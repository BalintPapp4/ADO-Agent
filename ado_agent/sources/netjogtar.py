"""Netjogtár (net.jogtar.hu) forrásadapter — friss változások és kulcs adótörvények."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..classifier import extract_effective_date, normalize_whitespace
from ..fetcher import DATE_RE, FetchResult
from ..models import RawCandidate
from .base import AdapterOutput, BaseSourceAdapter, parse_generic_response

LAW_HEADER_RE = re.compile(r"\d{4}\.\s*évi\s+[IVXLCDM]+\.\s*törvény|\d+/\d{4}\.\s*\([^)]+\)\s*Korm\.", re.IGNORECASE)
TEMPORAL_CUE_RE = re.compile(
    r"(?:hatályos|hatályba|módosít|módosul|beiktat|hatályon kívül|kihirdet|időállapot|változ|202[6-9]\.|203\d\.)",
    re.IGNORECASE,
)

# Ismert Netjogtár docid -> teljes magyar törvénycím + rövidítés kiegészítés
NETJOGTAR_KNOWN_TITLES: dict[str, str] = {
    "a0700127.tv": "2007. évi CXXVII. törvény - az általános forgalmi adóról (Áfa tv.)",
    "99500117.tv": "1995. évi CXVII. törvény - a személyi jövedelemadóról (Szja tv.)",
    "a0800067.tv": "2008. évi LXVII. törvény - az energiaellátók jövedelemadójáról (Robin Hood adó)",
    "99600081.tv": "1996. évi LXXXI. törvény - a társasági adóról és az osztalékadóról (Tao tv.)",
    "a1700150.tv": "2017. évi CL. törvény - az adózás rendjéről (Art.)",
    "a2200197.kor": "197/2022. (VI. 4.) Korm. rendelet az extraprofit adókról",
    "99100082.tv": "1991. évi LXXXII. törvény - a gépjárműadóról (Gjt.)",
    "99000100.tv": "1990. évi C. törvény - a helyi adókról (Htv.)",
    "99000093.tv": "1990. évi XCIII. törvény - az illetékekről (Itv.)",
    "a1700151.tv": "2017. évi CLI. törvény - az adóigazgatási rendtartásról (Air.)",
    "a1700153.tv": "2017. évi CLIII. törvény - az adóhatóság által foganatosítandó végrehajtási eljárásokról (Avt.)",
    "99400053.tv": "1994. évi LIII. törvény - a bírósági végrehajtásról (Vht.)",
    "a1800052.tv": "2018. évi LII. törvény - a szociális hozzájárulási adóról (Szocho tv.)",
    "a1900122.tv": "2019. évi CXXII. törvény - a társadalombiztosítás ellátásaira jogosultakról (Tbj.)",
    "a1200147.tv": "2012. évi CXLVII. törvény - a kisadózó vállalkozások tételes adójáról és a kisvállalati adóról (Kiva)",
    "a1600068.tv": "2016. évi LXVIII. törvény - a jövedéki adóról (Jöt.)",
    "a0000100.tv": "2000. évi C. törvény - a számvitelről (Szt.)",
}


class NetJogtarAdapter(BaseSourceAdapter):
    """Wolters Kluwer Netjogtár változásfigyelő és törvénymonitor."""

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        if "docid=" in res.final_url.lower():
            return self._parse_law_page(res)
        return parse_generic_response(res, out)

    def _parse_law_page(self, res: FetchResult) -> list[RawCandidate]:
        soup = BeautifulSoup(res.text, "lxml")
        h1 = soup.find("h1")
        title_tag = soup.find("title")
        heading = normalize_whitespace(h1.get_text(" ", strip=True) if h1 else "")
        page_title = normalize_whitespace(title_tag.get_text(" ", strip=True) if title_tag else "")
        page_title = re.sub(
            r"\s*[-–|]\s*(?:Hatályos Jogszabályok Gyűjteménye|Netjogtár).*$",
            "",
            page_title,
            flags=re.IGNORECASE,
        ).strip()

        docid_match = re.search(r"docid=([a-z0-9.]+)", res.final_url, re.IGNORECASE)
        known_title = NETJOGTAR_KNOWN_TITLES.get(docid_match.group(1).lower(), "") if docid_match else ""

        if heading and page_title and heading.lower() in page_title.lower() and len(page_title) > len(heading) + 4:
            title = page_title
        else:
            title = heading or page_title or known_title

        if known_title and title and len(title) < len(known_title) and title.lower() not in known_title.lower():
            # Ha az oldal csak a rövid számot adta vissza (pl. "1991. évi LXXXII. törvény"), egészítsük ki
            if not any(w in title.lower() for w in ("adó", "illeték", "végrehajt", "számvitel", "rendtartás")):
                title = known_title
        elif known_title and (not title or len(title) < 28):
            title = known_title

        if not title or len(title) < 6:
            return []

        for tag_name in ("script", "style", "noscript", "svg", "nav", "header", "footer", "aside"):
            for tag in soup.find_all(tag_name):
                tag.decompose()

        body_text = normalize_whitespace(soup.get_text(" ", strip=True))
        # Keressük a hatályosságra / jövőbeli időállapotra / módosításokra utaló részeket az egész oldalon
        priority_parts: list[str] = []
        general_parts: list[str] = []
        seen_low: set[str] = set()

        for el in soup.find_all(["h1", "h2", "h3", "p", "li", "tr", "option", "a", "div", "span"]):
            txt = normalize_whitespace(el.get_text(" ", strip=True))
            if not (10 <= len(txt) <= 260):
                continue
            low = txt.lower()
            if low == title.lower() or low in seen_low:
                continue
            if not TEMPORAL_CUE_RE.search(txt):
                continue
            seen_low.add(low)
            # Kiemeljük a konkrét évszámos / módosító törvényes sorokat előre
            if re.search(r"202[6-9]|203\d|módosít|hatályba|hatályon kívül", txt, re.I):
                priority_parts.append(txt)
            else:
                general_parts.append(txt)
            if len(priority_parts) >= 8 and len(general_parts) >= 6:
                break

        snippet_parts = (priority_parts + general_parts)[:6]
        summary = " | ".join(snippet_parts) if snippet_parts else body_text[:450]

        eff_date = extract_effective_date(title, " | ".join(priority_parts + general_parts))
        dm = DATE_RE.search(summary)
        pub = normalize_whitespace(dm.group(1)) if dm else ""
        doc_match = LAW_HEADER_RE.search(f"{title} {summary}")
        doc_ref = normalize_whitespace(doc_match.group(0)) if doc_match else ""

        return [
            RawCandidate(
                title=title,
                url=res.final_url,
                summary=summary[:800],
                published_at=pub,
                document_ref=doc_ref,
                status_label="Hatályos törvényszöveg (Netjogtár)",
                effective_date=eff_date,
                change_summary=priority_parts[:4],
            )
        ]
