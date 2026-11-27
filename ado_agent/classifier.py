"""Magyar és EU-s adózási szövegosztályozó és relevancia-pontozó motor."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
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
            "1991. évi lxxxii",
            "1990. évi c. törvény",
            "helyi adókról",
            "1990. évi xciii",
            "illetékekről",
            "2017. évi cli",
            "adóigazgatási rendtartás",
            "2017. évi cliii",
            "végrehajtási eljárás",
            "1994. évi liii",
            "bírósági végrehajtás",
            "2018. évi lii",
            "2019. évi cxxii",
            "2012. évi cxlvii",
            "2016. évi lxviii",
            "2000. évi c. törvény",
            "számvitelről",
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
            r"\bgjt\.?\b",
            r"\bhtv\.?\b",
            r"\bvht\.?\b",
            r"\bart\.?\b",
            r"\bair\.?\b",
            r"\bavt\.?\b",
            r"\bitv\.?\b",
            r"\btbj\.?\b",
            r"\bjöt\.?\b",
            r"\bszt\.?\b",
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


NAV_BOILERPLATE_RE = re.compile(
    r"Felhívjuk szíves figyelmét,\s*hogy ha a NAV következő oldalain.*?nem állapítható meg\.?"
    r"(?:\s*A fentiek alkalmazása.*?nem mentesít\.?)?",
    re.IGNORECASE | re.DOTALL,
)

NJT_BOILERPLATE_RE = re.compile(
    r"(?:Nemzeti Jogszabálytár\s+)?Ugrás a keresőre\s+Ugrás a tartalomra.*?"
    r"(?:EUR-LEX(?:\s+Nemzeti Jogszabálytár)*|Céginformációs Portál(?:\s+EUR-LEX)?(?:\s+Nemzeti Jogszabálytár)*)"
    r"(?:\s+Megnyitott j(?:ogszabályok)?)?",
    re.IGNORECASE | re.DOTALL,
)


def strip_nav_boilerplate(text: str) -> str:
    if not text:
        return ""
    cleaned = NAV_BOILERPLATE_RE.sub("", text)
    cleaned = NJT_BOILERPLATE_RE.sub("", cleaned)
    return normalize_whitespace(cleaned)


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# Magyar adó- és végrehajtási jogszabályok szabványos rövidítéseinek keresési feloldása
STATUTORY_ABBREVIATIONS: dict[str, tuple[str, ...]] = {
    "art": ("2017. evi cl.", "adozas rendjerol"),
    "gjt": ("1991. evi lxxxii.", "gepjarmuado", "cegautoado"),
    "htv": ("1990. evi c.", "helyi ado", "iparuzesi ado", "hipa"),
    "vht": ("1994. evi liii.", "birosagi vegrehajtas"),
    "air": ("2017. evi cli.", "adoigazgatasi rendtartas"),
    "avt": ("2017. evi cliii.", "adohatosag altal foganatositando"),
    "afa": ("2007. evi cxxvii.", "altalanos forgalmi ado"),
    "szja": ("1995. evi cxvii.", "szemelyi jovedelemado"),
    "tao": ("1996. evi lxxxi.", "tarsasagi ado"),
    "itv": ("1990. evi xciii.", "illetekekrol"),
    "tbj": ("2019. evi cxxii.", "tarsadalombiztositas"),
    "szocho": ("2018. evi lii.", "szocialis hozzajarulasi ado"),
    "kiva": ("2012. evi cxlvii.", "kisvallalati ado"),
    "kata": ("2022. evi xiii.", "kisadozo"),
    "jot": ("2016. evi lxviii.", "jovedeki ado"),
    "szt": ("2000. evi c.", "szamvitelrol"),
    "hpt": ("2013. evi ccxxxvii.", "hitelintezetekrol"),
    "hipa": ("helyi iparuzesi ado", "1990. evi c."),
    "neta": ("nepegeszsegugyi termekado",),
    "ekaer": ("elektronikus kozuti aruk",),
    "epr": ("kiterjesztett gyartoi felelosseg",),
    "hrt": (),
    "hvt": (),
}

_SHORT_WORD_BOUNDARY_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _abbr_word_pattern(tok_base: str) -> re.Pattern[str]:
    pat = _SHORT_WORD_BOUNDARY_RE_CACHE.get(tok_base)
    if pat is None:
        pat = re.compile(
            rf"\b{re.escape(tok_base)}(?:ban|ben|bol|rol|tol|hoz|nak|nek|ot|et|tal|tel|val|vel)?\b"
        )
        _SHORT_WORD_BOUNDARY_RE_CACHE[tok_base] = pat
    return pat


def match_hungarian_search(haystack: str, needle: str) -> bool:
    """Ékezet-, kötőjel-, pont/szóköz- és jogszabály-rövidítés-toleráns keresés."""
    if not needle:
        return True
    h_raw = strip_accents((haystack or "").lower())
    n_raw = strip_accents((needle or "").lower()).strip()
    if not n_raw:
        return True

    h_fold = re.sub(r"[-–—_/]+", " ", h_raw)
    n_fold = re.sub(r"[-–—_/]+", " ", n_raw)

    h_compact = re.sub(r"[^a-z0-9]", "", h_raw)
    n_compact = re.sub(r"[^a-z0-9]", "", n_raw)

    tokens = [t for t in n_fold.split() if t]
    if not tokens:
        return True

    has_sensitive_token = any(
        (t.strip(".,;:!?()[]{}") in STATUTORY_ABBREVIATIONS)
        or (len(t.strip(".,;:!?()[]{}")) <= 4 and t.strip(".,;:!?()[]{}").isalpha())
        for t in tokens
    )
    if not has_sensitive_token:
        if n_fold in h_fold:
            return True
        if n_compact and len(n_compact) >= 5 and n_compact in h_compact:
            return True

    for tok in tokens:
        tok_base = tok.strip(".,;:!?()[]{}")
        if not tok_base:
            continue

        if tok_base in STATUTORY_ABBREVIATIONS:
            expansions = STATUTORY_ABBREVIATIONS[tok_base]
            if _abbr_word_pattern(tok_base).search(h_fold):
                continue
            if any(
                exp in h_fold or re.sub(r"[^a-z0-9]", "", exp) in h_compact
                for exp in expansions
            ):
                continue
            return False

        if len(tok_base) <= 4 and tok_base.isalpha():
            if re.search(rf"\b{re.escape(tok_base)}", h_fold):
                continue
            return False

        tok_compact = re.sub(r"[^a-z0-9]", "", tok_base)
        if tok in h_fold or tok_base in h_fold or (tok_compact and tok_compact in h_compact):
            continue
        return False

    return True


def extract_document_ref(text: str) -> str:
    match = DOC_REF_RE.search(text or "")
    if not match:
        return ""
    return normalize_whitespace(match.group(1))


_MONTH_MAP: dict[str, int] = {
    "januar": 1,
    "january": 1,
    "februar": 2,
    "february": 2,
    "marcius": 3,
    "march": 3,
    "aprilis": 4,
    "april": 4,
    "majus": 5,
    "may": 5,
    "junius": 6,
    "june": 6,
    "julius": 7,
    "july": 7,
    "augusztus": 8,
    "august": 8,
    "szeptember": 9,
    "september": 9,
    "oktober": 10,
    "october": 10,
    "november": 11,
    "december": 12,
}

_EFFECTIVE_CONTEXT_RE = re.compile(
    r"(?:hatály\w*|életbe\s*lép\w*|lép\s+életbe|változ\w*|váltani\s+fog|módosul\w*|módosít\w*|"
    r"bevezet\w*|alkalmazandó|érvényes|időállapot|effective\s+from|shall\s+apply\s+from|"
    r"enters?\s+into\s+force|entry\s+into\s+force)",
    re.IGNORECASE,
)

_LEGISLATIVE_CHANGE_CUE_RE = re.compile(
    r"(?:törvény\w*|\btv\.?\b|módosít\w*|módosul\w*|változ\w*|hatály\w*|javaslat\w*|tervezet\w*|"
    r"rendelet\w*|irányelv\w*|directive|regulation|proposal|emelked\w*|csökken\w*|kedvezmény\w*)",
    re.IGNORECASE,
)

_NUM_DATE_RE = re.compile(r"\b(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})\.?")
_HU_MONTH_DATE_RE = re.compile(
    r"\b(20\d{2})\.?\s*(január|február|március|április|május|június|július|augusztus|"
    r"szeptember|október|november|december|january|february|march|april|may|june|july|"
    r"august|september|october|november|december)\w*(?:\s*(\d{1,2})\.?)?",
    re.IGNORECASE,
)
_EN_DMY_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+(january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\s+(20\d{2})\b",
    re.IGNORECASE,
)
_YEAR_ONLY_EFFECTIVE_RE = re.compile(
    r"\b(202[6-9]|203\d)(?:\s*[-–]?(?:től|tól|t[őo]l))?\s+(?:hatályos|hatályba\s+lép\w*|"
    r"lép\s+hatályba|változ\w*\s+fog|változik|módosul\w*|lép\s+életbe)",
    re.IGNORECASE,
)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        if 2000 <= year <= 2040:
            return date(year, month, day)
    except ValueError:
        return None
    return None


def extract_effective_date(
    title: str,
    summary: str = "",
    today: date | None = None,
) -> str:
    """Hatálybalépési / jogszabály-változási dátum kinyerése (ISO YYYY-MM-DD)."""
    ref_today = today or date.today()
    clean_text = strip_nav_boilerplate(f"{normalize_whitespace(title)} {normalize_whitespace(summary)}")
    if not clean_text:
        return ""

    has_change_cue = bool(_LEGISLATIVE_CHANGE_CUE_RE.search(clean_text))
    explicit_dates: list[date] = []
    future_dates: list[date] = []

    def consider(d: date | None, start: int, end: int) -> None:
        if d is None:
            return
        ctx_window = clean_text[max(0, start - 55) : min(len(clean_text), end + 55)]
        if _EFFECTIVE_CONTEXT_RE.search(ctx_window):
            explicit_dates.append(d)
        elif d > ref_today and has_change_cue:
            future_dates.append(d)

    for m in _NUM_DATE_RE.finditer(clean_text):
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        consider(d, m.start(), m.end())

    for m in _HU_MONTH_DATE_RE.finditer(clean_text):
        month_num = _MONTH_MAP.get(strip_accents(m.group(2).lower()))
        if month_num:
            day_num = int(m.group(3)) if m.group(3) else 1
            d = _safe_date(int(m.group(1)), month_num, day_num)
            consider(d, m.start(), m.end())

    for m in _EN_DMY_DATE_RE.finditer(clean_text):
        month_num = _MONTH_MAP.get(m.group(2).lower())
        if month_num:
            d = _safe_date(int(m.group(3)), month_num, int(m.group(1)))
            consider(d, m.start(), m.end())

    for m in _YEAR_ONLY_EFFECTIVE_RE.finditer(clean_text):
        d = _safe_date(int(m.group(1)), 1, 1)
        if d is not None:
            explicit_dates.append(d)

    all_candidates = explicit_dates + future_dates
    if not all_candidates:
        return ""

    upcoming = sorted(d for d in all_candidates if d > ref_today)
    if upcoming:
        return upcoming[0].isoformat()

    recent_explicit = sorted((d for d in explicit_dates if d <= ref_today), reverse=True)
    if recent_explicit and (ref_today - recent_explicit[0]).days <= 60:
        return recent_explicit[0].isoformat()

    return ""


def compute_effective_status(effective_date: str, today: date | None = None) -> str:
    """'upcoming' ha jövőbeli hatálybalépés, 'in_force' ha frissen (<=60 nap) hatályba lépett."""
    if not effective_date:
        return ""
    try:
        eff = date.fromisoformat(effective_date[:10])
    except ValueError:
        return ""
    ref_today = today or date.today()
    if eff > ref_today:
        return "upcoming"
    if (ref_today - eff) <= timedelta(days=60):
        return "in_force"
    return ""


_CHANGE_SENTENCE_CUE_RE = re.compile(
    r"(?:változ\w*|váltani|módosul\w*|módosít\w*|hatály\w*|életbe\s*lép\w*|bevezet\w*|"
    r"emelked\w*|csökken\w*|megszűn\w*|bővül\w*|kedvezmény\w*|mentesség\w*|értékhatár\w*|"
    r"kulcs\w*|százalék|%|ft\b|§|\d{4}\.\s*évi\s+[IVXLCDM]+|202[6-9]|203\d|com\s*\(\s*\d{4})",
    re.IGNORECASE,
)


# Mondathatár: nem vágja szét a magyar dátumokat (pl. 2027. január 1.),
# a római számokat (pl. (VI. 4.), CXXVII.), és a magyar jogi rövidítéseket (évi, Korm., tv., sz., stb.)
SENTENCE_SPLIT_RE = re.compile(
    r"[\n|•;]+|(?<![0-9])(?<![IVXLCDM])(?<!\bévi)(?<!\bÉvi)(?<!\btv)(?<!\bTv)(?<!\bsz)(?<!\bSz)"
    r"(?<!\bkorm)(?<!\bKorm)(?<!\brend)(?<!\bRend)(?<!\bbek)(?<!\bBek)(?<!\bdr)(?<!\bDr)"
    r"(?<!\bpl)(?<!\bPl)(?<!\bstb)(?<!\bStb)\.\s+"
)


def extract_change_summary(
    title: str,
    summary: str = "",
    effective_date: str = "",
    max_items: int = 4,
) -> list[str]:
    """Konkrét módosítási/változási pontok kinyerése a címből és összefoglalóból."""
    clean_title = normalize_whitespace(title)
    clean_summary = strip_nav_boilerplate(summary)
    if "NJT közvetlen jogszabály-figyelő" in clean_summary:
        clean_summary = ""

    raw_source = clean_summary if clean_summary else clean_title
    if not raw_source:
        return []

    parts = SENTENCE_SPLIT_RE.split(raw_source)

    bullets: list[str] = []
    seen_low: set[str] = set()

    def push_clause(clause: str) -> None:
        c = normalize_whitespace(clause).strip(" -–:|•")
        if len(c) < 14:
            return
        if c.lower() == clean_title.lower() and clean_summary:
            return
        if c.lower() not in seen_low:
            seen_low.add(c.lower())
            bullets.append(c[:240])

    for p in parts:
        p_clean = normalize_whitespace(p)
        if _CHANGE_SENTENCE_CUE_RE.search(p_clean):
            push_clause(p_clean)
            if len(bullets) >= max_items:
                break

    # Ha csak a cím hordozza a konkrét változás-bejelentést és a leírásból nem jött pont
    if not bullets and clean_title and _CHANGE_SENTENCE_CUE_RE.search(clean_title):
        push_clause(clean_title)

    # Ha van felismert hatálybalépési dátum, de a szövegből még nem került be dátumos sor
    if effective_date and not any(effective_date[:4] in b for b in bullets):
        formatted_date = effective_date.replace("-", ".") + "."
        bullets.insert(0, f"Hatálybalépés / változás időpontja: {formatted_date}")

    return bullets[:max_items]


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
    effective_date: str = ""
    effective_status: str = ""
    change_summary: list[str] = field(default_factory=list)


def _compile_custom_pattern(kw: str, use_accent_stripped: bool = False) -> re.Pattern[str]:
    """Magyar ragozás- és ékezetbarát regex egyéni kulcsszavakhoz."""
    target = strip_accents(kw) if use_accent_stripped else kw
    if not target:
        return re.compile(r"(?!x)x")
    prefix = r"\b" if target[0].isalnum() else ""
    if len(target) >= 3 and target[-1].lower() in ("a", "e"):
        stem = re.escape(target[:-1])
        tail = "[aá]" if target[-1].lower() == "a" else "[eé]"
        body = f"{stem}{tail}"
    else:
        body = re.escape(target)
    # 1-2 karakteres rövid szavaknál szigorú záró szóhatár, >=3 karakternél engedjük a magyar ragozást
    suffix = r"\b" if (target[-1].isalnum() and len(target) <= 2) else ""
    return re.compile(f"{prefix}{body}{suffix}", re.IGNORECASE)


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
        self._custom_patterns: list[tuple[str, re.Pattern[str], re.Pattern[str] | None]] = []
        for kw in self.custom_keywords:
            exact_pat = _compile_custom_pattern(kw, use_accent_stripped=False)
            stripped_kw = strip_accents(kw)
            accent_pat = (
                _compile_custom_pattern(kw, use_accent_stripped=True)
                if len(stripped_kw) >= 4
                else None
            )
            self._custom_patterns.append((kw, exact_pat, accent_pat))

    def classify(
        self,
        title: str,
        summary: str = "",
        url: str = "",
        jurisdiction: str = "HU",
        always_include_tax_context: bool = False,
        today: date | None = None,
    ) -> ClassificationResult:
        clean_title = normalize_whitespace(title)
        clean_summary = strip_nav_boilerplate(summary)
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

        # Egyéni felhasználói kulcsszavak (ragozás- és ékezet-toleráns illesztéssel)
        custom_hits: list[str] = []
        if self._custom_patterns:
            custom_search_text = f"{combined}\n{doc_ref}" if doc_ref else combined
            accent_search_text: str | None = None
            for kw, pat, accent_pat in self._custom_patterns:
                hit = bool(pat.search(custom_search_text))
                if not hit and accent_pat is not None:
                    if accent_search_text is None:
                        accent_search_text = strip_accents(custom_search_text)
                    hit = bool(accent_pat.search(accent_search_text))
                if hit:
                    custom_hits.append(kw)

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

        # Az egyéni kulcsszavakat garantáltan az elejére soroljuk, hogy a 18-as limit se vághassa le őket
        final_keywords: list[str] = []
        seen_final: set[str] = set()
        for kw in custom_hits + all_keywords:
            k_low = kw.lower()
            if k_low not in seen_final:
                seen_final.add(k_low)
                final_keywords.append(kw)

        eff_date = extract_effective_date(clean_title, clean_summary, today=today)
        eff_status = compute_effective_status(eff_date, today=today)
        changes = extract_change_summary(clean_title, clean_summary, effective_date=eff_date)

        return ClassificationResult(
            relevant=True,
            relevance_score=total_score,
            is_bill=is_bill,
            document_ref=doc_ref,
            category_matches=matches,
            matched_keywords=final_keywords[:18],
            effective_date=eff_date,
            effective_status=eff_status,
            change_summary=changes,
        )

    def enrich_candidate(
        self,
        candidate: RawCandidate,
        source: SourceConfig,
        today: date | None = None,
    ) -> LegislativeItem | None:
        result = self.classify(
            title=candidate.title,
            summary=candidate.summary,
            url=candidate.url,
            jurisdiction=source.jurisdiction,
            always_include_tax_context=source.always_include_tax_context,
            today=today,
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
        summary = strip_nav_boilerplate(candidate.summary)
        eff_date = candidate.effective_date or result.effective_date
        eff_status = compute_effective_status(eff_date, today=today) or result.effective_status

        merged_changes: list[str] = []
        seen_ch: set[str] = set()
        for line in list(candidate.change_summary or []) + list(result.change_summary or []):
            clean_line = normalize_whitespace(line)
            if clean_line and clean_line.lower() not in seen_ch:
                seen_ch.add(clean_line.lower())
                merged_changes.append(clean_line[:240])

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
            effective_date=eff_date,
            effective_status=eff_status,
            change_summary=merged_changes[:5],
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
