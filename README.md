# ADÓ Agent — Magyar és EU-s Adózási Törvényjavaslat-figyelő

Az **ADÓ Agent** egy **Windowsra (.exe)** és **macOS-re (.app + CLI)** egyaránt lefordítható, önállóan futtatható alkalmazás, amely figyeli és egy helyre gyűjti a magyar és európai uniós adózási törvényjavaslatokat, jogszabálytervezeteket és változásokat.

---

## Figyelt témakörök

Minden találatot automatikusan pontoz, kategorizál és kiemeli az egyező kulcsszavakat:

- **Robin Hood adó & Extraprofitadó** (`energiaellátók jövedelemadója`, `2008. évi LXVII. tv.`, `extraprofitadó`, `különadó`, `pótadó`, `bányajáradék`, `szolidaritási hozzájárulás`, `windfall tax`)
- **Személyi jövedelemadó (SZJA)** (`SZJA tv.`, `családi kedvezmény`, `cafeteria`, `béren kívüli juttatás`, `átalányadózás`, `TBSZ`, `osztalék`)
- **Visszatérítendő / Levonható ÁFA** (`visszatérítendő áfa`, `áfa-visszatérítés`, `áfa-visszaigénylés`, `levonható áfa`, `adólevonási jog`, `külföldi ÁFA-visszatérítés`, `VAT refund`)
- **Vissza nem térítendő / Nem levonható ÁFA** (`vissza nem térítendő áfa`, `nem levonható áfa`, `levonási tilalom`, `tárgyi/alanyi adómentesség`, `arányosítás`, `non-deductible VAT`)
- **ÁFA általános / eÁFA / ViDA** (`áfatörvény`, `online számla`, `eÁFA`, `fordított adózás`, `EU ViDA`)
- **Általános és egyéb adózás** (`TAO`, `KIVA`, `KATA`, `HIPA`, `Art.`, `szocho`, `jövedéki adó`, `tranzakciós illeték`, `globális minimumadó`, `EPR`)
- **EU Adójavaslatok & Irányelvek** (`COM` javaslatok, `Tanácsi irányelvek`, `DAC7/8/9`, `BEFIT`, `CBAM`, `Pillar Two`)
- **+ Egyéni kulcsszavak**: a felületről bármilyen saját szakterületi kifejezés hozzáadható.

---

## Figyelt források

| Forrás | Terület | Mit figyel? |
|---|---|---|
| **Országgyűlés** (`parlament.hu`) | HU | Benyújtott törvényjavaslatok (`T/` irományok), bizottsági anyagok |
| **Kormány.hu** (`kormany.hu`) | HU | Társadalmi egyeztetésre bocsátott tervezetek, dokumentumtár, minisztériumi hírek |
| **Netjogtár** (`net.jogtar.hu`) | HU | Jogszabályváltozások és főbb adótörvények (Áfa, SZJA, Robin Hood, TAO, Art.) |
| **Nemzeti Jogszabálytár** (`njt.hu`) | HU | Hivatalos zöld jogszabálytár kulcstörvény-figyelő |
| **NAV** (`nav.gov.hu` — *zöld*) | HU | Hivatalos adóhatósági hírek, jogszabályváltozások, RSS |
| **Magyar Közlöny** (`magyarkozlony.hu`) | HU | Friss közlöny számok és kihirdetett jogszabályok |
| **EUR-Lex / DG TAXUD / EP** (`eur-lex.europa.eu`) | EU | EU-s COM törvényjavaslatok, irányelvek, magyar és angol RSS/keresések |
| *Opcionális:* `adozona.hu`, `ado.hu` | HU | A „Források” menüben 1 kattintással bekapcsolhatóak, + saját RSS/web URL is felvehető |

---

## Letöltés és futtatás (Windows & Mac)

### 1. Előre fordított futtatható fájlok (GitHub Actions / Releases)

A `.github/workflows/build.yml` workflow minden feltöltéskor automatikusan lefordítja:
- **Windows:** `ADO-Agent-windows-x64.exe` (duplakattintásra elindul és megnyitja a böngészőben az irányítópultot)
- **macOS:** `ADO-Agent-macos.zip` (benne az `ADO-Agent.app` és a terminálos `ado-agent-cli`)
- **Linux:** `ADO-Agent-linux-x64`

> **Megjegyzés macOS esetén:** Mivel a közösségi/GitHub build nem rendelkezik fizetős Apple Developer tanúsítvánnyal, első indításkor a Gatekeeper figyelmeztethet: jobb klikk az `ADO-Agent.app`-ra → **Megnyitás** (vagy `xattr -cr ADO-Agent.app`).

### 2. Futtatás forráskódból (Fejlesztői mód)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Asztali webes felület indítása (automatikusan megnyitja a böngészőt):
python -m ado_agent

# Parancssori ellenőrzés és Excel export:
python -m ado_agent --scan --export jelentes.xlsx
```

### 3. Saját .exe / .app fordítása lokálisan

```bash
pip install -r requirements-dev.txt
python scripts/build_executable.py
```

A kész futtatható fájl a `release_artifacts/` mappába kerül.

---

## Főbb funkciók

- **Újdonság- és változásfigyelés (SQLite):** megjegyzi a korábbi ellenőrzéseket, így jelzi, mi az **ÚJ** vagy **FRISSÜLT**.
- **Fals-pozitív szűrés:** a magyar ragozott szavakra (`adózás`, `adótörvény`, `áfát`, `szja-ból`) illeszkedik, de kiszűri az olyan szavakat, mint az *eladó*, *kiadó*, *előadó*, *híradó*, valamint megkülönbözteti a *vissza nem térítendő támogatást* a *vissza nem térítendő ÁFA*-tól.
- **Exportálás:** egy kattintással formázott **Excel (`.xlsx`)**, magyar Excel-kompatibilis **CSV (`UTF-8 BOM`)**, **HTML riport**, **Markdown** vagy **JSON**.
- **Könyvjelzők és jegyzetek:** a fontos törvényjavaslatok megcsillagozhatók és megjegyzéssel láthatók el.
- **Adatmentés helye:** Windows alatt `%LOCALAPPDATA%\ADO-Agent`, macOS alatt `~/Library/Application Support/ADO-Agent`.
