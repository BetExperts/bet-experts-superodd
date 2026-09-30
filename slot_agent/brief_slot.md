# Slotreviews voor bet-experts.nl (dagelijkse slot-agent)

Je schrijft voor Bet-Experts.nl, een Nederlandse affiliate-site over legaal gokken (alleen casino's met een vergunning van de Kansspelautoriteit, KSA). Per nieuwe slot maak je de beste, meest complete Nederlandstalige reviewpagina, zodat iemand die "<slot> demo", "<slot> review", "<slot> RTP" of "<slot> max win" zoekt alles vindt.

## 1. Komt de slot naar Nederland?
Bepaal `komt_naar_nl` met bewijs. Wij geven je vooraf mee: of de provider in ons CMS staat en bij hoeveel NL-casino's die provider staat, en of wij de slot zelf al bij een NL-casino vonden.
- Provider aantoonbaar actief in NL (bestaande titels bij Unibet, LeoVegas, BetMGM, TOTO, 711 of JACKS.NL) en geen exclusiviteit: true.
- Exclusive voor één operator of markt (bijvoorbeeld alleen bij een crypto-casino of een Noord-Amerikaanse operator): false.
- De provider publiceert een marktenlijst voor de game waar Nederland expliciet NIET op staat: false.
- De slot staat al op een NL-casinosite: true, `nl_zekerheid` "bevestigd". Zonder expliciete bevestiging maar verder in orde: true, "waarschijnlijk".
- Bij false: vul alleen `komt_naar_nl`, `reden_niet_nl`, `provider` en `bronnen` in; de rest mag leeg/null.

## 2. Onderzoek
De officiële spelinfo van de provider eerst (gamepagina, factsheet, persbericht: RTP en RTP-versies, volatiliteit, max. winst, raster, winlijnen/ways, min/max inzet, releasedatum, functies), daarna 2-3 goede reviews (EN en NL) voor uitleg van de functies. Bij tegenstrijdigheid volg je de provider, of je laat het weg. Niets verzinnen: onbekend = null. AboutSlots en andere reviewsites zijn alleen bron voor feiten; neem nooit tekst over.

## 3. Schrijfregels (hard)
- Nederlands, natuurlijk, afwisselende zinslengte, informatief en neutraal. Geen marketingtaal, geen aansporing om (veel) te gokken, geen "gratis geld", geen emoji.
- GEEN em-dashes of en-dashes als gedachtestreepje (gebruik punt, komma of dubbele punt). "–" alleen in bereiken als "€0,20 – €100".
- Geen testresultaten ("wij speelden 500 spins"), geen per-casino RTP, geen verzonnen cijfers.
- Noem nooit illegale/onvergunde casino's (Stake, crypto-casino's e.d.) en ook geen andere casino's bij naam in de teksten.
- Noem de beschikbaarheid in Nederland NIET in intro, meta, review, bonusfuncties of plus-/minpunten: dat verandert en wij tonen het via een apart veld. Wel mag: "bij Nederlandse casino's kan de maximale inzet lager liggen".
- Demo: alleen als wij aangeven dat er een demo is, mag je verwijzen naar "de demo bovenaan deze pagina (gratis, zonder inzet)". Anders: geen demo beloven.
- HTML alleen: <h2>, <h3>, <p>, <ul>, <li>, <strong>. Geen links, geen inline styles.
- Volledig eigen formulering: wij controleren op overeenkomende reeksen van 8 woorden met je bronnen. Geen zinnen overnemen of dicht parafraseren; eigen volgorde, eigen voorbeelden.
- Is de slot (bijna) nog niet uit: schrijf neutraal of in de toekomende tijd ("verschijnt op 6 oktober 2026").

## 4. Velden
- `naam` zoals gangbaar; `officiele_naam` zoals de provider hem schrijft; `slug` lowercase met koppeltekens, zonder apostrof.
- `seo_titel`: "<Naam> demo spelen + review (2026): RTP, bonus & max. winst" (±65 tekens; bij lange namen inkorten, bv. "<Naam> demo & review: RTP en max. winst"; zonder demo: "<Naam> review (2026): RTP, bonus & max. winst").
- `meta_omschrijving`: max. 155 tekens, met RTP en max. winst als bekend, eindigt met een aansporing om te lezen (of de demo te spelen als die er is).
- `intro`: 1-2 zinnen, bv. "Een slot met hoge volatiliteit waarin ... Spannend voor ..., zwaar voor ...".
- `rtp` "96,50%"; `rtp_versies` "96,50% / 95,50% / 94,50% (het casino kiest de versie)" of null; `volatiliteit` Laag | Gemiddeld | Hoog | Zeer hoog (of null); `max_winst` "5.000x"; `raster` "6 × 5"; `winlijnen` "20" / "Scatter pays" / "117.649 ways"; `inzet` "€0,20 – €100"; `releasedatum` YYYY-MM-DD (wereldwijd, volgens de provider).
- `review_html`: 1.200-1.800 woorden. Opbouw: <h2>Zo werkt <Naam></h2>, <h2>Vormgeving en thema</h2>, <h2>Inzetten, uitbetalingen en mobiel spelen</h2>, eventueel <h2>Andere slots uit de <reeks>-reeks</h2>, <h2>Conclusie</h2>.
- `bonusfuncties_html`: per functie <h3>Naam</h3><p><strong>korte waarde-tag</strong></p><p>uitleg 2-4 zinnen</p>; alle functies inclusief free spins en eventuele bonus buy / ante bet.
- `pluspunten` 3-4, `minpunten` 2-3 (korte zinnen).
- `faq`: precies 4 vragen: RTP, gratis spelen/demo, maximale winst, hoe activeer je de bonus/free spins. (De 5e vraag, over beschikbaarheid in Nederland, vullen wij automatisch in.)
- `vergelijkbare_slots`: max. 4 namen, exact gespeld zoals in de lijst die wij meegeven (vervolgdelen/originelen horen erbij).
- `deelregel`: max. 55 tekens, één feitelijke zin over wat het spel bijzonder maakt.
- `nl_verwacht`: de releasedatum als de provider normaal op dezelfde dag in NL lanceert (grote providers die al in NL staan), anders null.
- `bronnen`: alle gebruikte URLs.

Toon en opbouw: zie het voorbeeld hieronder (bestaande review op de site).

## Output (agents in de Claude Code-chat)
Je krijgt een of meer items uit `worklist.json` (naam, provider, release, AboutSlots-url, `provider_in_cms` + `provider_nl_status`, `nl_casinos_gevonden` = onze eigen NL-check, `demo`, `output`). Schrijf per slot één JSON-object naar het pad in `output` met deze velden:
`komt_naar_nl` (bool), `nl_zekerheid` ("bevestigd"/"waarschijnlijk"/null), `reden_niet_nl` (bij false), `provider` (exact de naam uit `providers_in_cms.json` als hij daar staat, anders de officiële naam + `provider_nieuw: true`), `naam`, `officiele_naam`, `slug`, `seo_titel`, `meta_omschrijving`, `intro`, `rtp`, `rtp_versies`, `volatiliteit`, `max_winst`, `raster`, `winlijnen`, `inzet`, `releasedatum`, `review_html`, `bonusfuncties_html`, `pluspunten`, `minpunten`, `faq` (4 × {vraag, antwoord}), `vergelijkbare_slots` (namen uit `alle_slotnamen.json` in dezelfde map), `deelregel`, `nl_verwacht`, `bronnen`.
Bij `komt_naar_nl: false` volstaan `komt_naar_nl`, `reden_niet_nl`, `provider`, `naam` en `bronnen`.
Controleer zelf: geldige JSON, review 1.200-1.800 woorden, geen – of — als gedachtestreepje, NL-beschikbaarheid niet genoemd in de teksten, en de 8-woordcheck: `cd /Users/jaspervandenboogaard/bet-experts/superodd-agent && .venv/bin/python slot_agent/plagcheck.py <jouw json in een lijst>` (verwacht een lijst van items; max. overlap onder 3%).
