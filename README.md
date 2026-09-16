# Bet365 Super-Odd-agent

Crawlt dagelijks de **Super Boost** (Super Odd) van [bet365.nl](https://www.bet365.nl),
maakt er een promotieartikel van in de Webflow **Promoties**-collectie (rubriek
**SuperOdd**, bookmaker **Bet365**), publiceert het **live** en stuurt een
**Telegram**-bericht met de link.

> Volledig losstaand van `telegram_agent`. Hergebruikt alleen dezelfde
> `TELEGRAM_BOT_TOKEN` + kanaal `@BetExpertsGroup`, geen gedeelde code of state.

## Alleen de Super Boost (niet de Bet Boosts)
Bet365 toont meerdere boosts. De agent pakt **uitsluitend** de Super Boost, te
herkennen aan de badge-afbeelding `SuperBoostBadges/Super-Boost-*.svg` (Bet
Boosts gebruiken `BetBoostBadgesMono/Bet-Boost-*.svg`). Er staat er precies één.

## Bestanden
| Bestand | Doel |
|---|---|
| `so_crawl.py` | Playwright-crawl van bet365.nl → Super-Boost-data |
| `so_build.py` | Bouwt de Webflow-velddata (titel, content, checks, stappen, voorwaarden) |
| `so_webflow.py` | Create/update + direct publiceren via Webflow API v2 |
| `so_telegram.py` | Telegram-bericht met knop naar het artikel |
| `generate.py` | Orchestratie (crawl → CMS live → Telegram), idempotent per dag |
| `so_config.py` | Alle id's, links en instellingen |
| `.github/workflows/generate.yml` | Dagelijkse cron via GitHub Actions |

## Vaste id's (al ingevuld in `so_config.py`)
- Promoties-collectie: `65e6fb5b08aed95b983b590f`
- Rubriek **SuperOdd**: `6aaa9afdf92f60c1aeff6a58`
- Bookmaker **Bet365**: `651bd6728c40de720bd8072a`
- Bet365-affiliatelink: `…affiliate=365_02599619`

## Secrets (GitHub → Settings → Secrets and variables → Actions)
- `WEBFLOW_TOKEN` — je Webflow API-token (zelfde als je andere agents)
- `TELEGRAM_BOT_TOKEN` — zelfde bot als `telegram_agent`
- (optioneel) variabele `TELEGRAM_CHANNEL` — laat leeg voor `@BetExpertsGroup`
- (optioneel) `TELEGRAM_TEST_CHAT` — voor `--test`

## Lokaal draaien
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python generate.py --dry          # alleen crawlen + tonen
python generate.py --test         # live in CMS + Telegram naar TEST-chat
python generate.py                # live in CMS + Telegram naar het kanaal
```

## Evergreen + uurlijks (SEO)
- **Eén vast CMS-item per bookmaker** (slug `bet365-super-odd`) dat elk uur wordt
  bijgewerkt — beter voor SEO dan elke dag een nieuw item (bouwt autoriteit op
  één URL, geen duplicaten, geen opschonen nodig).
- Draait **elk uur** (`cron: 15 * * * *`). Public repo = onbeperkte Actions-minuten.
- Wijzigingslogica per run:
  - **nieuwe wedstrijd** (nieuwe Super Boost) → artikel bijwerken **+ Telegram**
  - alleen **odd/selectie** gewijzigd → artikel stil bijwerken (**geen** Telegram)
  - niets gewijzigd → niets doen (geen republish)
- State (`state/superodd.json`) bewaart per bookmaker: item-id, laatste wedstrijd
  en een handtekening (match|oude odd|nieuwe odd|selecties).

## Let op
- **GitHub Actions draait op datacenter-IP's.** Bet365 kan die blokkeren of
  geo-weigeren. Lukt de crawl niet op Actions, dan draait de agent wél op een
  NL-/residentieel IP (bv. je eigen Mac via cron, of Actions + NL-proxy).
- Meer bookmakers later = extra config-blok + eigen vaste slug/state-sleutel.

## Tweede agent: TOTO 50x je inzet (`toto50x.py`)
Crawlt dagelijks `toto.nl/welkomstbonus/sport`, leest de 50x-wedstrijd van vandaag
(bv. "winst Juventus of winst NEC" → Juventus - NEC), en werkt **alleen de titel**
van het bestaande CMS-item `toto-50x-je-inzet` bij. Bij een **nieuwe wedstrijd**
stuurt hij één Telegram-bericht: de TOTO 50x-afbeelding (`assets/toto-50x.jpg`) met
een teaser-bijschrift + knop naar het artikel.
- Bestanden: `toto_config/crawl/build/telegram.py` + `toto50x.py`, state `state/toto50x.json`.
- Mac: `run_toto.sh` + LaunchAgent `com.betexperts.toto50x` (08:45-22:45).
- Draait op de Mac (TOTO laadt vanaf NL-IP; net als Bet365 niet vanaf datacenter).
