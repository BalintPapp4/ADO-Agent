"""Magyar és EU-s adózási szövegosztályozó és relevancia-pontozó motor."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .models import CategoryMatch, LegislativeItem, RawCandidate, SourceConfig


@dataclass(frozen=True)
class CategoryRule:
    id: str
    name: str
    description: str
    color: str
    weight: int
    phrases: tuple[str, ...]
    patterns: tuple[str, ...] = ()


# Alapértelmezett magyar + EU adózási kategóriák
CATEGORY_RULES: tuple[CategoryRule, ...] = (
    CategoryRule(
        id="robin_hood",
        name="Robin Hood adó & Extraprofitadó",
        description="Energiaellátók jövedelemadója, extraprofitadók, különadók, pótadók, bányajáradék, szolidaritási hozzájárulás.",
        color="#d97706",
        weight=35,
        phrases=(
            "robin hood",
            "robin-hood",
            "robinhood",
            "energiaellátók jövedelemadója",
            "energiaellátók adója",
            "2008. évi lxvii",
            "extraprofit",
            "extraprofitadó",
            "különadó",
            "pótadó",
            "197/2022",
            "bányajáradék",
            "szolidaritási hozzájárulás",
            "kiskereskedelmi adó",
            "távközlési pótadó",
            "biztosítási pótadó",
            "gyógyszergyártói különadó",
            "légitársaságok hozzájárulása",
            "windfall tax",
            "solidarity contribution",
            "energy solidarity",
            "excess profit",
        ),
        patterns=(
            r"\brobin[\s\-]?hood\b",
            r"\bextraprofit\w*\b",
            r"\bkülönadó\w*\b",
            r"\bpótadó\w*\b",
            r"\benergiaellátó\w*\s+jövedelemadó\w*\b",
        ),
    ),
    CategoryRule(
        id="szja",
        name="Személyi jövedelemadó (SZJA)",
        description="SZJA tv., családi kedvezmények, cafeteria, béren kívüli juttatások, átalányadózás, befektetési/osztalékjövedelem.",
        color="#2563eb",
        weight=32,
        phrases=(
            "személyi jövedelemadó",
            "szja",
            "1995. évi cxvii",
            "családi kedvezmény",
            "családi adókedvezmény",
            "első házasok kedvezménye",
            "személyi kedvezmény",
            "25 év alatti",
            "30 év alatti anyák",
            "négy vagy több gyermeket nevelő",
            "cafeteria",
            "béren kívüli juttatás",
            "egyes meghatározott juttatás",
            "átalányadózás",
            "átalányadó",
            "szja-visszatérítés",
            "szja visszatérítés",
            "tbsz",
            "tartós befektetési számla",
            "osztalékadó",
            "árfolyamnyereség",
            "kamatjövedelem",
            "personal income tax",
        ),
        patterns=(
            r"\bszja\w*\b",
            r"\bszemélyi\s+jövedelemadó\w*\b",
            r"\bátalányadó\w*\b",
        ),
    ),
    CategoryRule(
        id="afa_visszateritendo",
        name="Visszatérítendő / Levonható ÁFA",
        description="ÁFA-visszatérítés, áfa-visszaigénylés, adólevonási jog, előzetesen felszámított adó, külföldi ÁFA-visszatérítés.",
        color="#059669",
        weight=38,
        phrases=(
            "visszatérítendő áfa",
            "áfa-visszatérítés",
            "áfa visszatérítés",
            "áfa-visszaigénylés",
            "áfa visszaigénylés",
            "visszaigényelhető áfa",
            "levonható áfa",
            "adólevonási jog",
            "levonási jog",
            "előzetesen felszámított adó",
            "kiutalási határidő",
            "külföldi áfa-visszatérítés",
            "külföldi áfa visszatérítés",
            "lakásáfa-visszatérítés",
            "lakásáfa visszatérítés",
            "áfa-visszatérítési",
            "vat refund",
            "refund of vat",
            "deductible vat",
            "right to deduct",
            "input vat",
            "vat recovery",
            "eighth directive",
            "thirteenth directive",
        ),
        patterns=(
            r"visszatérítendő\s+(?:általános\s+forgalmi\s+adó|áfá|áfa)\w*",
            r"(?:áfa|áfá)[\s\-]?visszatérítés\w*",
            r"(?:áfa|áfá)[\s\-]?visszaigénylés\w*",
            r"visszaigényelhető\s+(?:általános\s+forgalmi\s+adó|áfá|áfa)\w*",
            r"(?:levonható\s+áfa|adólevonási\s+jog)\w*",
        ),
    ),
    CategoryRule(
        id="afa_nem_visszateritendo",
        name="Vissza nem térítendő / Nem levonható ÁFA",
        description="Vissza nem térítendő ÁFA, levonási tilalom, nem levonható ÁFA, tárgyi/alanyi adómentesség, arányosítás.",
        color="#dc2626",
        weight=38,
        phrases=(
            "vissza nem térítendő áfa",
            "vissza nem térítendő általános forgalmi adó",
            "nem levonható áfa",
            "vissza nem igényelhető áfa",
            "nem visszaigényelhető áfa",
            "levonási tilalom",
            "adólevonási tilalom",
            "levonási hányados",
            "arányosítás",
            "tárgyi adómentesség",
            "tárgyi adómentes",
            "alanyi adómentesség",
            "alanyi adómentes",
            "non-deductible vat",
            "irrecoverable vat",
            "non-refundable vat",
            "vat deduction restriction",
            "exempt from vat",
        ),
        patterns=(
            r"vissza\s+nem\s+térítendő\s+(?:általános\s+forgalmi\s+adó|áfá|áfa)\w*",
            r"nem\s+levonható\s+(?:általános\s+forgalmi\s+adó|áfá|áfa)\w*",
            r"(?:adó)?levonási\s+tilal\w+",
        ),
    ),
    CategoryRule(
        id="afa_altalanos",
        name="ÁFA általános / eÁFA / ViDA",
        description="Áfa tv., áfakulcsok, fordított adózás, online számla, eÁFA, EU ViDA (ÁFA a digitális korban).",
        color="#0d9488",
        weight=26,
        phrases=(
            "általános forgalmi adó",
            "áfatörvény",
            "áfa-törvény",
            "áfa tv",
            "2007. évi cxxvii",
            "eáfa",
            "e-áfa",
            "online számla",
            "fordított adózás",
            "áfa-kulcs",
            "áfakulcs",
            "5%-os áfa",
            "18%-os áfa",
            "27%-os áfa",
            "value added tax",
            "vat directive",
            "vat in the digital age",
            "ioss",
            "egyablakos rendszer",
        ),
        patterns=(
            r"\báfa\b",
            r"\báfá(?:t|val|nak|ban|ról|ból|ra|hoz|ig|ért|jú|s|k|i)\b",
            r"\báfa-[a-záéíóöőúüű]+\b",
            r"\bvat\b",
            r"\bvida\b",
        ),
    ),
    CategoryRule(
        id="egyeb_ado",
        name="Adózás általános (TAO, KIVA, HIPA, Art., stb.)",
        description="Általános adótörvények, TAO, KIVA, KATA, HIPA, Art., szocho, jövedéki, illeték, globális minimumadó, EPR.",
        color="#4f46e5",
        weight=22,
        phrases=(
            "adózás",
            "adózási",
            "adótörvény",
            "adócsomag",
            "adómódosítás",
            "adómérték",
            "adóalap",
            "adókedvezmény",
            "adómentesség",
            "adóbírság",
            "adóbevallás",
            "adóeljárás",
            "adózás rendjéről",
            "adóigazgatási",
            "2017. évi cl",
            "társasági adó",
            "1996. évi lxxxi",
            "kisvállalati adó",
            "kiva",
            "kata",
            "2022. évi xiii",
            "helyi iparűzési adó",
            "hipa",
            "szociális hozzájárulási adó",
            "szocho",
            "jövedéki adó",
            "tranzakciós illeték",
            "pénzügyi tranzakciós illeték",
            "vagyonszerzési illeték",
            "népegészségügyi termékadó",
            "globális minimumadó",
            "transzferár",
            "gépjárműadó",
            "cégautóadó",
            "reklámadó",
            "építményadó",
            "telekadó",
            "termékdíj",
            "adóhatóság",
            "corporate income tax",
            "corporate tax",
            "local business tax",
            "excise duty",
            "taxation",
            "tax law",
            "tax code",
            "tax rate",
            "tax relief",
            "tax exemption",
            "tax base",
        ),
        patterns=(
            # Ragozott és összetett magyar 'adó...' szavak szóhatáron — kizárva az eladó/kiadó/előadó/híradó szavakat!
            r"\badó(?:z[aáeéiíoóöőuúüű]*|t|val|vel|nak|nek|ban|ben|ból|ből|ról|ről|ra|re|hoz|hez|höz|ig|ért|ként|s|k|i|alap\w*|bevallás\w*|bírság\w*|csalás\w*|csomag\w*|előleg\w*|ellenőrz\w*|eljárás\w*|fizetés\w*|hatóság\w*|hitel\w*|igazgat\w*|jog\w*|kedvezmény\w*|kötelez\w*|kulcs\w*|mentes\w*|mérték\w*|módosít\w*|nem\w*|nyilvántart\w*|pótlék\w*|rendszer\w*|szabály\w*|szám\w*|tartozás\w*|terhel\w*|törvény\w*|ügyi\w*|változás\w*|visszaigény\w*)?\b",
            r"\btao\b",
            r"\bkiva\b",
            r"\bkata\b",
            r"\bhipa\b",
            r"\bszocho\b",
            r"\bneta\b",
            r"\badó-\s*[a-záéíóöőúüű]+\b",
        ),
    ),
    CategoryRule(
        id="eu_ado",
        name="EU Adójavaslatok & Irányelvek",
        description="EU COM javaslatok, tanácsi irányelvek, DAC7/8/9, BEFIT, Pillar Two, CBAM, ViDA, Unshell, FASTER.",
        color="#0284c7",
        weight=24,
        phrases=(
            "tanácsi irányelv",
            "európai bizottság javaslata",
            "council directive",
            "proposal for a council directive",
            "proposal for a regulation",
            "eu tax",
            "tax directive",
            "administrative cooperation",
            "dac7",
            "dac8",
            "dac9",
            "befit",
            "pillar two",
            "globe",
            "cbam",
            "karbonvám",
            "unshell",
            "faster directive",
            "debra",
            "transfer pricing directive",
            "minimum taxation",
            "digital services tax",
            "fiscal policy",
        ),
        patterns=(
            r"\bcom\s*\(\s*\d{4}\s*\)\s*\d+\b",
            r"\bdac\s*[789]\b",
        ),
    ),
)

# Törvényjavaslat / jogalkotási jelzők (bónusz pontszám és "Törvényjavaslat" jelölés)
BILL_PATTERNS: tuple[str, ...] = (
    r"\btörvényjavaslat\w*\b",
    r"\btörvénytervezet\w*\b",
    r"\bjogszabálytervezet\w*\b",
    r"\btársadalmi\s+egyeztetés\w*\b",
    r"\bmódosításáról\s+szóló\b",
    r"\bországgyűlési\s+iromány\w*\b",
    r"\b[THKJB]/\d{3,6}(?:/\d+)?\b",
    r"\bcom\s*\(\s*\d{4}\s*\)\s*\d+\b",
    r"\bproposal\s+for\s+a\s+(?:council\s+)?(?:directive|regulation|decision)\b",
    r"\bdraft\s+(?:law|bill|directive|regulation)\b",
    r"\birányelv[\s\-]?javaslat\w*\b",
    r"\brendelet[\s\-]?tervezet\w*\b",
)

# Gyakori fals-pozitív szavak — önmagukban nem jelenthetnek adózást
FALSE_POSITIVE_WORDS: tuple[str, ...] = (
    "eladó",
    "kiadó",
    "előadó",
    "feladó",
    "híradó",
    "rádióadó",
    "tévéadó",
    "televízióadó",
    "családgondozó",
)

# Contextual rule: "vissza nem térítendő" önmagában (ÁFA nélkül) gyakran támogatás!
# Csak akkor minősül "vissza nem térítendő ÁFA"-nak, ha ÁFA/VAT/levonás szövegkörnyezet is jelen van.
NON_REFUNDABLE_GENERIC_RE = re.compile(r"vissza\s+nem\s+térítendő", re.IGNORECASE)
VAT_CONTEXT_RE = re.compile(
    r"\b(?:áfa|áfá\w*|általános\s+forgalmi\s+adó\w*|vat|levonás\w*|adólevon\w*|előzetesen\s+felszámított)\b",
    re.IGNORECASE,
)

# EU dokumentumazonosító vagy magyar T/xxxxx irományszám kinyerése
DOC_REF_RE = re.compile(
    r"\b([THKJB]/\d{3,6}(?:/\d+)?|COM\s*\(\d{4}\)\s*\d+|\d{4}\.\s*évi\s+[IVXLCDM]+\.\s*(?:törvény|tv\.?)|\d{1,4}/\d{4}\.\s*\([^)]+\)\s*Korm\.\s*rendelet)\b",
    re.IGNORECASE,
)


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_document_ref(text: str) -> str:
    match = DOC_REF_RE.search(text or "")
    if not match:
        return ""
    return normalize_whitespace(match.group(1))


def compute_item_key(source_id: str, url: str, title: str) -> str:
    clean_url = (url or "").strip()
    parsed = urlparse(clean_url)
    has_specific_target = bool(parsed.path.strip("/") or parsed.query)
    if has_specific_target:
        canonical = f"{source_id}|{clean_url.lower()}"
    else:
        canonical = f"{source_id}|{clean_url.lower()}|{strip_accents(normalize_whitespace(title)).lower()}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def compute_content_hash(title: str, summary: str, published_at: str, status_label: str) -> str:
    payload = "|".join(
        [
            normalize_whitespace(title),
            normalize_whitespace(summary),
            normalize_whitespace(published_at),
            normalize_whitespace(status_label),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


@dataclass
class ClassificationResult:
    relevant: bool
    relevance_score: int
    is_bill: bool
    document_ref: str
    category_matches: list[CategoryMatch] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)


class TaxClassifier:
    """Rugalmas osztályozó beépített + felhasználói kulcsszavakkal."""

    def __init__(self, custom_keywords: list[str] | None = None) -> None:
        self.custom_keywords = [
            normalize_whitespace(kw) for kw in (custom_keywords or []) if normalize_whitespace(kw)
        ]
        self._compiled_rules: list[tuple[CategoryRule, list[re.Pattern[str]]]] = []
        for rule in CATEGORY_RULES:
            pats: list[re.Pattern[str]] = []
            for p in rule.patterns:
                pats.append(re.compile(p, re.IGNORECASE))
            for phrase in rule.phrases:
                escaped = re.escape(phrase)
                # Szóhatár az elején és végén, kivéve ha írásjellel végződik (pl. 'com(')
                prefix = r"\b" if phrase[0].isalnum() else ""
                suffix = r"\b" if phrase[-1].isalnum() else ""
                pats.append(re.compile(f"{prefix}{escaped}{suffix}", re.IGNORECASE))
            self._compiled_rules.append((rule, pats))

        self._bill_patterns = [re.compile(p, re.IGNORECASE) for p in BILL_PATTERNS]
        self._custom_patterns = [
            (
                kw,
                re.compile(
                    (r"\b" if kw[0].isalnum() else "")
                    + re.escape(kw)
                    + (r"\b" if kw[-1].isalnum() else ""),
                    re.IGNORECASE,
                ),
            )
            for kw in self.custom_keywords
        ]

    def classify(
        self,
        title: str,
        summary: str = "",
        url: str = "",
        jurisdiction: str = "HU",
        always_include_tax_context: bool = False,
    ) -> ClassificationResult:
        clean_title = normalize_whitespace(title)
        clean_summary = normalize_whitespace(summary)
        combined = f"{clean_title}\n{clean_summary}".strip()
        if not combined:
            return ClassificationResult(relevant=False, relevance_score=0, is_bill=False, document_ref="")

        # Dokumentumszám kinyerése
        doc_ref = extract_document_ref(combined) or extract_document_ref(url)

        # Törvényjavaslat / tervezet detektálása
        is_bill = any(pat.search(combined) for pat in self._bill_patterns)
        if not is_bill and url:
            if re.search(r"/(iromany|torvenyjavaslat|tarsadalmi-egyeztetes|proposal)", url, re.IGNORECASE):
                is_bill = True

        matches: list[CategoryMatch] = []
        all_keywords: list[str] = []
        seen_kw_lower: set[str] = set()

        def add_kw(kw: str) -> None:
            k_low = kw.lower()
            if k_low not in seen_kw_lower:
                seen_kw_lower.add(k_low)
                all_keywords.append(kw)

        for rule, patterns in self._compiled_rules:
            cat_hits: list[str] = []
            seen_cat_hits: set[str] = set()
            title_hits = 0

            for pat in patterns:
                for m in pat.finditer(combined):
                    hit_text = normalize_whitespace(m.group(0))
                    if not hit_text:
                        continue
                    low = hit_text.lower()
                    if low in FALSE_POSITIVE_WORDS:
                        continue
                    if low not in seen_cat_hits:
                        seen_cat_hits.add(low)
                        cat_hits.append(hit_text)
                        if pat.search(clean_title):
                            title_hits += 1

            # Speciális kontextuális check: "vissza nem térítendő" támogatás vs ÁFA
            if rule.id == "afa_nem_visszateritendo" and not cat_hits:
                if NON_REFUNDABLE_GENERIC_RE.search(combined) and VAT_CONTEXT_RE.search(combined):
                    cat_hits.append("vissza nem térítendő (+ÁFA kontextus)")
                    if NON_REFUNDABLE_GENERIC_RE.search(clean_title):
                        title_hits += 1

            if cat_hits:
                cat_score = rule.weight + min(len(cat_hits) - 1, 4) * 6 + min(title_hits, 3) * 8
                matches.append(
                    CategoryMatch(
                        category_id=rule.id,
                        category_name=rule.name,
                        score=cat_score,
                        matched_keywords=cat_hits[:10],
                    )
                )
                for kw in cat_hits[:10]:
                    add_kw(kw)

        # Egyéni felhasználói kulcsszavak
        custom_hits: list[str] = []
        for kw, pat in self._custom_patterns:
            if pat.search(combined):
                custom_hits.append(kw)
                add_kw(kw)

        if custom_hits:
            matches.append(
                CategoryMatch(
                    category_id="egyeni",
                    category_name="Egyéni kulcsszavak",
                    score=30 + min(len(custom_hits) - 1, 4) * 6,
                    matched_keywords=custom_hits,
                )
            )

        # Ha EU-s forrásból jött és van adózási találat, de az eu_ado kategória még nincs benne,
        # jelezzük az EU jelleget ha javaslatról van szó
        has_any_tax = len(matches) > 0
        if jurisdiction == "EU" and has_any_tax and not any(m.category_id == "eu_ado" for m in matches):
            if is_bill or re.search(r"\b(eu|directive|regulation|európai|tanács|bizottság|irányelv)\b", combined, re.I):
                matches.append(
                    CategoryMatch(
                        category_id="eu_ado",
                        category_name="EU Adójavaslatok & Irányelvek",
                        score=20,
                        matched_keywords=["EU jogalkotás"],
                    )
                )

        # Ha dedikált adóhatósági forrás (pl. NAV) és egy általános adóhírről van szó,
        # de a szöveg rövid és mégis adóhoz kapcsolódik
        if not matches and always_include_tax_context and len(clean_title) >= 8:
            # NAV esetén is csak értelmes elemeket veszünk fel (nem menüpontokat)
            if re.search(r"\b(adó|áfa|szja|tao|kiva|bevallás|számla|járulék|illeték|jövedéki|határidő|jogszabály|tájékoztató)\w*\b", combined, re.I):
                matches.append(
                    CategoryMatch(
                        category_id="egyeb_ado",
                        category_name="Adózás általános (TAO, KIVA, HIPA, Art., stb.)",
                        score=18,
                        matched_keywords=["NAV / adóhatósági tájékoztató"],
                    )
                )
                add_kw("NAV / adóhatósági tájékoztató")

        if not matches:
            return ClassificationResult(
                relevant=False,
                relevance_score=0,
                is_bill=is_bill,
                document_ref=doc_ref,
                category_matches=[],
                matched_keywords=[],
            )

        # Összpontszám kiszámítása 0..100 skálán
        raw_score = max(m.score for m in matches) + max(0, len(matches) - 1) * 10
        if is_bill:
            raw_score += 15
        if doc_ref:
            raw_score += 8
        total_score = min(100, raw_score)

        # Fontosság szerinti sorrend
        matches.sort(key=lambda m: m.score, reverse=True)

        return ClassificationResult(
            relevant=True,
            relevance_score=total_score,
            is_bill=is_bill,
            document_ref=doc_ref,
            category_matches=matches,
            matched_keywords=all_keywords[:15],
        )

    def enrich_candidate(
        self,
        candidate: RawCandidate,
        source: SourceConfig,
    ) -> LegislativeItem | None:
        result = self.classify(
            title=candidate.title,
            summary=candidate.summary,
            url=candidate.url,
            jurisdiction=source.jurisdiction,
            always_include_tax_context=source.always_include_tax_context,
        )
        if not result.relevant:
            return None

        doc_ref = candidate.document_ref or result.document_ref
        status_label = candidate.status_label
        if not status_label:
            if result.is_bill:
                status_label = "Törvényjavaslat / Tervezet"
            elif source.jurisdiction == "EU":
                status_label = "EU jogalkotási elem"
            else:
                status_label = "Jogszabály / Tájékoztató"

        title = normalize_whitespace(candidate.title)
        summary = normalize_whitespace(candidate.summary)
        item_key = compute_item_key(source.id, candidate.url, title)
        content_hash = compute_content_hash(title, summary, candidate.published_at, status_label)

        return LegislativeItem(
            item_key=item_key,
            title=title,
            url=candidate.url,
            source_id=source.id,
            source_name=source.name,
            jurisdiction=source.jurisdiction,
            summary=summary,
            published_at=normalize_whitespace(candidate.published_at),
            document_ref=doc_ref,
            status_label=status_label,
            relevance_score=result.relevance_score,
            is_bill=result.is_bill,
            categories=[m.category_id for m in result.category_matches],
            category_names=[m.category_name for m in result.category_matches],
            matched_keywords=result.matched_keywords,
            content_hash=content_hash,
            raw_metadata=candidate.raw_metadata,
        )


def get_category_catalog() -> list[dict[str, str]]:
    """UI számára a kategóriák metaadatai."""
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "color": r.color,
        }
        for r in CATEGORY_RULES
    ] + [
        {
            "id": "egyeni",
            "name": "Egyéni kulcsszavak",
            "description": "A felhasználó által hozzáadott egyedi kulcsszavak.",
            "color": "#7c3aed",
        }
    ]
