"""Nemzeti Jogszabálytár (njt.hu — hivatalos lap) forrásadapter."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..classifier import (
    extract_change_summary,
    extract_effective_date,
    normalize_whitespace,
    strip_nav_boilerplate,
)
from ..fetcher import DATE_RE, FetchResult, is_spa_empty_shell
from ..models import RawCandidate
from .base import AdapterOutput, BaseSourceAdapter, parse_generic_response

NJT_LAW_TITLES = {
    "2007-127-00-00": "2007. évi CXXVII. törvény az általános forgalmi adóról (Áfa tv.)",
    "1995-117-00-00": "1995. évi CXVII. törvény a személyi jövedelemadóról (Szja tv.)",
    "2008-67-00-00": "2008. évi LXVII. törvény (Robin Hood adó — energiaellátók jövedelemadója)",
    "1996-81-00-00": "1996. évi LXXXI. törvény a társasági adóról és az osztalékadóról (Tao tv.)",
    "2017-150-00-00": "2017. évi CL. törvény az adózás rendjéről (Art.)",
    "2022-197-20-22": "197/2022. (VI. 4.) Korm. rendelet az extraprofit adókról",
    "1991-82-00-00": "1991. évi LXXXII. törvény a gépjárműadóról (Gjt.)",
    "1990-100-00-00": "1990. évi C. törvény a helyi adókról (Htv.)",
    "1990-93-00-00": "1990. évi XCIII. törvény az illetékekről (Itv.)",
    "2017-151-00-00": "2017. évi CLI. törvény az adóigazgatási rendtartásról (Air.)",
    "2017-153-00-00": "2017. évi CLIII. törvény az adóhatóság által foganatosítandó végrehajtási eljárásokról (Avt.)",
    "1994-53-00-00": "1994. évi LIII. törvény a bírósági végrehajtásról (Vht.)",
    "2018-52-00-00": "2018. évi LII. törvény a szociális hozzájárulási adóról (Szocho tv.)",
    "2019-122-00-00": "2019. évi CXXII. törvény a társadalombiztosítás ellátásaira jogosultakról (Tbj.)",
    "2012-147-00-00": "2012. évi CXLVII. törvény a kisadózó vállalkozások tételes adójáról és a kisvállalati adóról (Kiva tv.)",
    "2016-68-00-00": "2016. évi LXVIII. törvény a jövedéki adóról (Jöt.)",
    "2000-100-00-00": "2000. évi C. törvény a számvitelről (Szt.)",
}


class NjtAdapter(BaseSourceAdapter):
    """Nemzeti Jogszabálytár (njt.jog.gov.hu) figyelő."""

    def collect(self) -> AdapterOutput:
        out = AdapterOutput()
        urls: list[str] = []
        seen_u: set[str] = set()
        for raw in [self.source.url, *self.source.extra_urls]:
            u = raw.strip()
            if u and u not in seen_u:
                seen_u.add(u)
                urls.append(u)

        for url in urls:
            out.checked_urls.append(url)
            res = self.fetcher.fetch(url)
            if not res.ok:
                # Automatikus tükör-fallback njt.jog.gov.hu <-> njt.hu között
                mirror = ""
                if "njt.jog.gov.hu" in url:
                    mirror = url.replace("njt.jog.gov.hu", "njt.hu")
                elif "njt.hu" in url:
                    mirror = url.replace("njt.hu", "njt.jog.gov.hu")
                if mirror and mirror not in seen_u:
                    seen_u.add(mirror)
                    out.checked_urls.append(mirror)
                    res_mirror = self.fetcher.fetch(mirror)
                    if res_mirror.ok:
                        res = res_mirror
                    else:
                        out.errors.append(f"{url}: {res.error}")
                        continue
                else:
                    out.errors.append(f"{url}: {res.error}")
                    continue

            out.ok_requests += 1
            items = self.parse_response(res, out)
            out.candidates.extend(items)
        return out

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        if "/jogszabaly/" in res.final_url.lower():
            return self._parse_njt_law_page(res, out)
        return parse_generic_response(res, out)

    def _parse_njt_law_page(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        # Ha Angular SPA üres héjként jön le JS nélkül, a törvényazonosító alapján is megőrizzük a figyelő linket,
        # ha viszont SSR/meta adat van benne, kinyerjük a navigációs fejléc nélkül!
        soup = BeautifulSoup(res.text, "lxml")
        is_spa = is_spa_empty_shell(res.text)

        meta_desc = soup.find("meta", attrs={"name": "description"})
        title_tag = soup.find("title")
        h1 = soup.find("h1")
        slug = res.final_url.rstrip("/").split("/")[-1]
        fallback_title = NJT_LAW_TITLES.get(slug, "")

        raw_title = normalize_whitespace(
            (h1.get_text(" ", strip=True) if h1 else "")
            or (title_tag.get_text(" ", strip=True) if title_tag else "")
        )
        raw_title = re.sub(r"\s*[-–|]\s*Nemzeti Jogszabálytár\s*$", "", raw_title, flags=re.I).strip()

        # Navigációs / portálfejléc elemek biztonságos eltávolítása a szöveg kinyerése előtt
        for tag_name in ("script", "style", "noscript", "svg", "nav", "header", "footer", "aside"):
            for tag in list(soup.find_all(tag_name)):
                if tag.parent is not None and not tag.find("h1"):
                    tag.decompose()
        for el in list(soup.find_all(attrs={"role": re.compile(r"^(navigation|banner|contentinfo)$", re.I)})):
            if el.parent is not None and not el.find("h1"):
                el.decompose()
        for el in list(
            soup.find_all(
                class_=re.compile(
                    r"\b(?:skip-?links?|breadcrumbs?|site-header|portal-header|site-footer|navbar|nav-menu|sidebar-nav)\b",
                    re.I,
                )
            )
        ):
            if el.parent is not None and not el.find("h1") and len(el.get_text(" ", strip=True)) < 2500:
                el.decompose()

        # Ha csak generikus "Nemzeti Jogszabálytár" a cím (SPA), használjuk az ismert nevet
        if not raw_title or raw_title.lower() in {"nemzeti jogszabálytár", "njt", "njt.jog.gov.hu"}:
            raw_title = fallback_title
        elif fallback_title and len(fallback_title) > len(raw_title) + 4 and fallback_title.split()[0] in raw_title:
            raw_title = fallback_title

        if not raw_title:
            return []

        desc = strip_nav_boilerplate(normalize_whitespace(meta_desc.get("content", "") if meta_desc else ""))
        main_el = (
            soup.find("main")
            or soup.find(attrs={"role": "main"})
            or soup.find(id=re.compile(r"(content|jogszabaly|law)", re.I))
            or soup.find(class_=re.compile(r"(jogszabaly|law-content|main-content)", re.I))
            or soup.body
            or soup
        )
        body_text = strip_nav_boilerplate(normalize_whitespace(main_el.get_text(" ", strip=True)))
        eff_date = ""
        changes: list[str] = []

        if is_spa:
            summary = desc or (
                "NJT közvetlen jogszabály-figyelő (kliensoldali felület; "
                "kattints a linkre a legfrissebb hatályos szöveghez)."
            )
            if not any("SPA" in w or "Angular" in w for w in out.warnings):
                out.warnings.append(
                    "Az njt.jog.gov.hu kliensoldali alkalmazást használ — a kulcstörvények közvetlen linkjei "
                    "felvételre kerültek, de a teljes keresési lista csak böngészőben töltődik be."
                )
        else:
            summary = desc or body_text[:700]
            eff_date = extract_effective_date(raw_title, body_text[:2000])
            changes = extract_change_summary(raw_title, body_text[:2500], effective_date=eff_date)

        dm = DATE_RE.search(summary)
        pub = normalize_whitespace(dm.group(1)) if dm else ""
        doc_match = re.search(
            r"(\d{4}\.\s*évi\s+[IVXLCDM]+\.\s*törvény|\d+/\d{4}\.\s*\([^)]+\)\s*Korm\.\s*rendelet)",
            raw_title,
            re.I,
        )

        return [
            RawCandidate(
                title=raw_title,
                url=res.final_url,
                summary=summary[:800],
                published_at=pub,
                document_ref=normalize_whitespace(doc_match.group(1)) if doc_match else "",
                status_label="Nemzeti Jogszabálytár",
                effective_date=eff_date,
                change_summary=changes,
            )
        ]
