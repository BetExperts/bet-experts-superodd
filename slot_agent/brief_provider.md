# Casino providerpagina's voor bet-experts.nl (dagelijkse slot-agent)

Er is een nieuwe slot van een provider die nog niet op onze site staat. Maak een complete providerpagina in dezelfde stijl en met dezelfde velden als de bestaande providers (voorbeeld hieronder).

Regels:
- Nederlands, feitelijk, eigen woorden (wij controleren op 8-woordreeksen uit je bronnen), geen em-/en-dashes als gedachtestreepje, geen aansporing tot gokken, niets verzinnen (onbekend = null).
- Noem geen casino's bij naam, en nooit onvergunde/illegale casino's.
- Veel kleine studio's distribueren via Games Global, Relax Gaming (Silver Bullet) of Hacksaw (OpenRGS): noem dat als het klopt.
- `over-de-provider`: 140-200 woorden in 3 alinea's (<p>…</p><p>…</p><p>…</p>): oprichting, eigenaar/distributie, licenties als bevestigd, bekendste titels en eigen mechanieken, aanwezigheid in NL (volgens de gegevens die wij meegeven).
- `spelaanbod-per-soort` en `rtp-en-volatiliteit`: 80-120 woorden, elk in 2 alinea's.
- `status-nederland`: zie Output hieronder (zelf controleren).
- Top 3: `top-3-titel` "Top 3 slots van <naam>", `top-slot-1..3` (namen) en `top-slot-N-tekst` (45-70 woorden, eigen woorden, met RTP/volatiliteit/max. winst/releasejaar alleen als betrouwbaar bekend). Neem de nieuwe slot op als die bij de bekendste hoort, anders de 3 bekendste titels.
- Scores (tekst met komma, 1 decimaal, schaal 1-10): `spelaanbod-score` (500+ spellen en meerdere soorten 9+; 200-400 ±8; 100-200 ±7-7,5; <100 6-7), `gemiddelde-rtp-score` (≥96,5% 9,0; ±96% 8,5; ±95,5% 8,0; ±95% 7,5; ±94% 6,5-7), `innovatie-score` (trendsetter 9+; eigen herkenbare mechaniek 8; degelijk maar volgend 7; vooral klassiek 6-6,5).
- Overige velden: `name`, `slug`, `seo-titel` (in de stijl van het voorbeeld), `meta-omschrijving` (≤155), `intro` (1-2 zinnen), `opgericht`, `hoofdkantoor`, `aantal-spellen` (bv. "70+"), `gemiddelde-rtp`, `bekend-van` (3 titels, komma), `spelsoorten` (met " · "), `sterke-punten` (<ul><li>, 3) en `minder-sterke-punten` (<ul><li>, 1-2), `faq-1..5-vraag/antwoord` (legaal in NL?, bekendste spel?, live casino?, RTP?, waar spelen?), `officiele-website`, `deelregel` (≤85 tekens), `bronnen`.

## Output (agents in de Claude Code-chat)
Schrijf alle nieuwe providers van de run als JSON-lijst naar `providers.json` in de run-map (naast `worklist.json`), met de Webflow-veldslugs hierboven als keys plus `bronnen` en `slotslaunch-provider-id` (zoek op in `/Users/jaspervandenboogaard/bet-experts/superodd-agent/state/sl_providers.json`, of null). `status-nederland`: controleer 3-5 bekende titels via de spelpagina's (Unibet /play/<slug>, LeoVegas /game/<slug>, BetMGM /casino/slots/<slug>, TOTO casino.toto.nl/casino/games/<slug>, 711 /casino/<provider>/<slug>, JACKS /casino/slots/<slug>; 200 + naam in titel = aanwezig, test een nep-slug op 404) en schrijf "Bij X van de 6 gecontroleerde vergunde casino's" of "Niet gevonden bij de gecontroleerde vergunde casino's".
