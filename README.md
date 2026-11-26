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
| **Nemzeti Jogszabálytár** (`njt.hu` — *zöld*) | HU | Hivatalos zöld jogszabálytár kulcstörvény-figyelő |
| **NAV** (`nav.gov.hu` — *zöld*) | HU | Hivatalos adóhatósági hírek, jogszabályváltozások, RSS |
| **Magyar Közlöny** (`magyarkozlony.hu` — *zöld*) | HU | Friss közlöny számok és kihirdetett jogszabályok |
| **EUR-Lex / DG TAXUD / EP** (`eur-lex.europa.eu`) | EU | EU-s COM törvényjavaslatok, irányelvek, magyar és angol RSS/keresések |
| *Opcionális:* `adozona.hu`, `ado.hu` | HU | A „Források” menüben 1 kattintással bekapcsolhatóak, + saját RSS/web URL is felvehető |

---

## Letöltés és futtatás (Windows & Mac — 1 kattintással!)

### 1. Előre fordított futtatható fájlok (GitHub Actions / Releases)

A `.github/workflows/build.yml` workflow minden feltöltéskor automatikusan lefordítja:
- **Windows (`ADO-Agent-windows-x64`):**
  - `ADO-Agent-windows-x64.exe` — közvetlen indítás (megnyitja a böngészőt és automatikusan frissít)
  - `Inditas-Windows.bat` — 1 kattintásos Windows CMD indító (`.exe`-vel vagy forráskódból automatikus `.venv` telepítéssel)
  - `ADO-Agent-CMD-Segito.bat` — interaktív Windows CMD menü (webes indítás, azonnali Excel export, forráslistázás, adatmappa)
- **macOS (`ADO-Agent-macos`):**
  - `ADO-Agent.app` — duplakattintásos macOS alkalmazás
  - `ado-agent-cli` — Terminálból hívható bináris
  - `Inditas-Mac.command` — 1 kattintásos macOS Terminal indító (automatikus Gatekeeper `xattr` feloldással!)
  - `ADO-Agent-Mac-Terminal-Segito.command` — interaktív macOS Terminal menü
- **Linux (`ADO-Agent-linux-x64`):** önálló futtatható bináris

> **1 kattintásos Asztali parancsikon:** Az alkalmazás tetején a **„⌘ Indítók (CMD / Mac)”** gombra kattintva közvetlenül az Asztalodra is létrehozhatod vagy letöltheted a saját gépedre szabott Windows `.bat` vagy macOS `.command` parancsikonokat!

### 2. Futtatás forráskódból (Fejlesztői mód vagy letöltött ZIP)

- **Windows:** dupla kattintás az `Inditas-Windows.bat` vagy az `ADO-Agent-CMD-Segito.bat` fájlra.
- **macOS:** dupla kattintás az `Inditas-Mac.command` vagy az `ADO-Agent-Mac-Terminal-Segito.command` fájlra (első letöltés után ha nem indul: `chmod +x *.command`).

Vagy kézzel parancssorból:

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
