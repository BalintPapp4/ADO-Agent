"""Tesztek minden magyar és EU-s forrásadapterhez mockolt HTTP válaszokkal."""

from __future__ import annotations

from pathlib import Path

import httpx

from ado_agent.config import AppConfig, get_default_sources
from ado_agent.fetcher import HttpFetcher
from ado_agent.scanner import TaxScanner
from ado_agent.storage import Database


MOCK_PARLAMENT_HTML = """
<html><body>
  <table>
    <tr>
      <td><a href="/iromanyok/T_10888">T/10888</a></td>
      <td>Egyes adótörvények, így a személyi jövedelemadó és az ÁFA módosításáról szóló törvényjavaslat</td>
      <td>2026.11.20.</td>
    </tr>
    <tr>
      <td><a href="/iromanyok/T_10889">T/10889</a></td>
      <td>A közúti közlekedésről szóló törvény módosítása</td>
      <td>2026.11.19.</td>
    </tr>
  </table>
</body></html>
"""

MOCK_KORMANY_HTML = """
<html><head></head><body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "documents": [
        {
          "title": "Társadalmi egyeztetés: Az extraprofitadó és a Robin Hood adó 2027. évi szabályairól szóló tervezet",
          "url": "/dokumentumtar/extraprofitado-tervezet-2027",
          "lead": "Az energiaellátók jövedelemadója és a különadók kivezetésének ütemezése.",
          "publishedAt": "2026-11-22"
        },
        {
          "title": "Sportcsarnok felújítási program",
          "url": "/dokumentumtar/sportcsarnok",
          "lead": "Kulturális és sportberuházások."
        }
      ]
    }
  }
}
</script>
</body></html>
"""

MOCK_NETJOGTAR_LAW_HTML = """
<html>
<head><title>2008. évi LXVII. törvény - Netjogtár</title></head>
<body>
  <h1>2008. évi LXVII. törvény a távhőszolgáltatás versenyképesebbé tételéről (Robin Hood adó)</h1>
  <p>Hatályos: 2026.11.15. Módosította a 2026. évi L. törvény az energiaellátók jövedelemadójáról.</p>
</body>
</html>
"""

MOCK_NJT_SPA_HTML = """
<html>
<head><title>Nemzeti Jogszabálytár</title></head>
<body><app-root></app-root></body>
</html>
"""

MOCK_NAV_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>NAV Hírek</title>
    <item>
      <title>Változik a visszatérítendő és a vissza nem térítendő ÁFA nyilvántartása</title>
      <link>https://nav.gov.hu/ado/afa-valtozas-2026</link>
      <description>Útmutató az áfa-visszaigénylés és a levonási tilalom alkalmazásához.</description>
      <pubDate>Thu, 20 Nov 2026 09:00:00 +0100</pubDate>
    </item>
  </channel>
</rss>
"""

MOCK_KOZLONY_HTML = """
<html><body>
  <div class="list">
    <a href="/kozlony/2026-145.pdf">Magyar Közlöny 2026. évi 145. szám — Az adózás rendjéről és az SZJA-ról szóló törvény kihirdetése</a>
    <span>2026.11.21.</span>
  </div>
</body></html>
"""

MOCK_EURLEX_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>EUR-Lex EU Tax Proposals</title>
    <item>
      <title>COM(2026) 310 Proposal for a Council Directive amending VAT refund and DAC9 tax rules</title>
      <link>https://eur-lex.europa.eu/legal-content/HU/TXT/?uri=COM:2026:310:FIN</link>
      <description>EU directive proposal on deductible VAT and corporate taxation.</description>
      <pubDate>Wed, 18 Nov 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def _mock_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "parlament.hu" in url:
        return httpx.Response(200, text=MOCK_PARLAMENT_HTML, headers={"content-type": "text/html; charset=utf-8"})
    if "kormany.hu" in url:
        return httpx.Response(200, text=MOCK_KORMANY_HTML, headers={"content-type": "text/html; charset=utf-8"})
    if "net.jogtar.hu" in url:
        if "docid=" in url:
            return httpx.Response(200, text=MOCK_NETJOGTAR_LAW_HTML, headers={"content-type": "text/html; charset=utf-8"})
        return httpx.Response(200, text="<html><body><a href='/hirek/1'>ÁFA tv. frissítés 2026</a></body></html>", headers={"content-type": "text/html"})
    if "njt.hu" in url:
        return httpx.Response(200, text=MOCK_NJT_SPA_HTML, headers={"content-type": "text/html; charset=utf-8"})
    if "nav.gov.hu" in url:
        return httpx.Response(200, text=MOCK_NAV_RSS, headers={"content-type": "application/rss+xml; charset=utf-8"})
    if "magyarkozlony.hu" in url:
        return httpx.Response(200, text=MOCK_KOZLONY_HTML, headers={"content-type": "text/html; charset=utf-8"})
    if "eur-lex.europa.eu" in url or "europarl.europa.eu" in url or "taxation-customs" in url:
        return httpx.Response(200, text=MOCK_EURLEX_RSS, headers={"content-type": "application/rss+xml; charset=utf-8"})
    return httpx.Response(404, text="Not found")


def test_full_scanner_across_all_builtin_sources(tmp_path: Path):
    cfg = AppConfig(data_dir=tmp_path, sources=get_default_sources())
    db = Database(cfg.db_path)

    client = httpx.Client(transport=httpx.MockTransport(_mock_handler))
    fetcher = HttpFetcher(client=client)
    scanner = TaxScanner(cfg, db, fetcher=fetcher)

    summary = scanner.run_scan()

    assert summary.total_sources == 7  # 7 alapértelmezett aktív forrás
    assert summary.failed_sources == 0
    assert summary.total_matched >= 7
    assert summary.new_items == summary.total_matched

    items = db.query_items()
    source_ids = {it.source_id for it in items}
    assert "parlament_hu" in source_ids
    assert "kormany_hu" in source_ids
    assert "net_jogtar_hu" in source_ids
    assert "njt_hu" in source_ids
    assert "nav_gov_hu" in source_ids
    assert "magyar_kozlony" in source_ids
    assert "eur_lex_eu" in source_ids

    # Nem adós cikkek (sportcsarnok, közúti közlekedés) ne kerüljenek be!
    titles = " | ".join(it.title.lower() for it in items)
    assert "sportcsarnok" not in titles
    assert "közúti közlekedés" not in titles

    # Második futtatás változatlan tartalommal -> 0 új
    summary2 = scanner.run_scan()
    assert summary2.new_items == 0
    assert summary2.updated_items == 0


def test_partial_network_failure_does_not_crash_other_sources(tmp_path: Path):
    def flaky_handler(request: httpx.Request) -> httpx.Response:
        if "parlament.hu" in str(request.url):
            return httpx.Response(503, text="Service Unavailable")
        return _mock_handler(request)

    cfg = AppConfig(data_dir=tmp_path, sources=get_default_sources())
    db = Database(cfg.db_path)
    client = httpx.Client(transport=httpx.MockTransport(flaky_handler))
    scanner = TaxScanner(cfg, db, fetcher=HttpFetcher(client=client))

    summary = scanner.run_scan()
    assert summary.failed_sources == 1
    assert summary.succeeded_sources >= 1
    assert summary.total_matched >= 5


def test_nav_boilerplate_and_megamenu_not_attached_to_links():
    from ado_agent.fetcher import extract_html_candidates

    html = """
    <html><body>
      <nav class="main-menu">
        <a href="/ugyfeliranytu">Ügyféliránytű</a>
        <span>Adó kulcsok tárgyi adómentes tevékenységek Szociális hozzájárulási adó</span>
      </nav>
      <div class="disclaimer-box">
        Felhívjuk szíves figyelmét, hogy ha a NAV következő oldalain 2018. január 1-je után közzétett
        tájékoztatóknak megfelelően jár el, akkor az adózás rendjéről szóló 2017. évi CL. törvény 247. §-a
        alapján jogkövetkezmény az Ön részére nem állapítható meg. A fentiek alkalmazása az esetleges adóhiány megfizetése alól nem mentesít.
        <a href="/ugyfeliranytu/jogszabaly">Ügyféliránytű részletek</a>
      </div>
      <article class="news-card">
        <h3><a href="/ado/uj-szja-szabaly">Új SZJA családi adókedvezmény 2027</a></h3>
        <p>Fontos változások a személyi jövedelemadóban.</p>
      </article>
    </body></html>
    """
    cands = extract_html_candidates(html, "https://nav.gov.hu/ado")
    titles = [c.title for c in cands]
    assert "Ügyféliránytű" not in titles  # nav-ból kiszűrve
    szja = [c for c in cands if "SZJA" in c.title]
    assert len(szja) == 1
    assert "2017. évi CL." not in szja[0].summary
    discl = [c for c in cands if "Ügyféliránytű részletek" in c.title]
    if discl:
        assert "2017. évi CL." not in discl[0].summary
