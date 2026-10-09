# BörstNyheter – gratis nyhetsbot för Discord

Boten hämtar nyheter från svenska och amerikanska källor (plus Reddit), filtrerar bort brus och postar det intressanta i din Discord. Den körs gratis av GitHub Actions var 10:e minut. Ingen server behövs.


## Anpassa
- **Dina bolag**: öppna `bolag.txt` på GitHub (pennikonen), skriv ett bolag per rad och spara med **Commit changes**. Boten söker då specifikt efter dem, även amerikanska bolagsrapporter (SEC 8-K).
- **Källor och nyckelord**: ändra i `config.py`. Där finns även `MAX_AGE_HOURS` och `MAX_POSTS_PER_RUN`.
- **Färger**: 🟢 positiv, 🔴 negativ, ⚪ neutral. Sentimentet bygger på nyckelord (eller på AI om du aktiverat det), så det kan ha fel.

## Felsökning
- **Inget kommer i Discord**: kolla loggen i Actions. Står det `FEL: Hemligheten DISCORD_WEBHOOK saknas` har steg 4 inte blivit rätt (namnet måste vara exakt).
- **`Permission denied` / push misslyckas**: gör om steg 5.
- **Körningarna slutar komma efter en tid**: GitHub pausar schemalagda körningar i repon som inte haft aktivitet på länge. Gå till **Actions** och klicka **Enable workflow**.
- **För mycket spam**: minska `MAX_POSTS_PER_RUN` eller ta bort breda källor i `config.py`.
- **Du missar nyheter**: körningarna kan försenas några minuter, och gratiskällor har ingen garanti för fullständighet. Boten är ett komplement till egen bevakning.

---

# Del 2 – Spike-skannern (kortsiktiga kandidater)

Skannern är din skanner-prompt omskriven till kod, så den kan köras gratis och automatiskt. Den ersätter inte nyhetsboten utan körs vid sidan av den (`scanner.yml`, var 5:e minut vardagar under börs- och pre-markettid).

## Vad den gör
1. **Hittar kandidater** med Yahoos screener: USA (0,50-20 USD, börsvärde under 300 mn USD, +2 % och uppåt, volym över 100 000), samt Sverige, Norge, Danmark och Finland med motsvarande filter i lokal valuta. Aktier du lägger i `scanner_watchlist.txt` analyseras alltid.
2. **Analyserar minutdata** för de mest ovanliga: tidsjusterad relativ volym (jämförs med samma klockslag de senaste dagarna), volymacceleration, kursändring senaste 1/5/15 minuterna, utbrott över de senaste 30 minuternas högsta, falska utbrott, avstånd till dagens högsta, spread och omsättning.
3. **Kollar nyheter** (Yahoo, reserv Google News): hittar viktigaste nyheten de senaste 24 timmarna och jämför tidpunkten med när kursen började röra sig. Kom nyheten efter rörelsen märks den som möjlig efterhandsförklaring. Hittas ingen nyhet står det **SPEKULATIV RÖRELSE, ORSAK EJ BEKRÄFTAD**.
4. **Utspädning**: letar efter ord som offering, warrants, convertible, reverse split, nyemission i rubrikerna. Utöver det är utspädning **OKÄND** och du får en länk till SEC-filings att kolla själv.
5. **Poäng 0-100** enligt din modell (volym 25, utbrott 20, nyhet 20, tidigt skede 15, håller nivån 10, likviditet 10) och klassificering: TIDIG SIGNAL, UTBROTT PÅGÅR, NYHETSDRIVEN, SPEKULATIV, REDAN RUSAT, HÖG RISK.
6. **Varnar i Discord** när poängen är minst 65 (justerbart i `scanner_config.py`). Aktier som redan rusat varnar den bara för vid minst 85. Samma aktie varnas inte om igen inom en timme om inte poängen stigit 10 steg eller utbrott precis inletts.
7. **Utvärderar sig själv**: varje varning loggas i `signals_log.json`, och kursen noteras efter 15 min, 30 min, 1 tim, dagens slut och nästa dag. Varje kväll efter 22.30 svensk tid postas en rapport med träffprocent, median, snitt och sämsta utfall. Du kan också köra rapporten manuellt: `python scanner.py --rapport`.

## Så aktiverar du den
1. Följ stegen ovan. Skannern kommer med i samma zip, och `scanner.yml` ligger i `.github/workflows/`.
2. (Valfritt) Skapa en egen Discord-kanal och webhook för skannern och lägg in den som secret `DISCORD_WEBHOOK_SCANNER`.
3. Gå till **Actions**, välj **Spike-skanner** och klicka **Run workflow**. Är marknaderna stängda står det i loggen `stängd just nu, hoppar över`, vilket är rätt.
4. Läs loggen första gången. Raden `[USA] screener: 23 träffar` betyder att datan funkar. Står det att screenern misslyckades blockerar Yahoo troligen GitHubs servrar just då, vilket du kan försöka igen på senare.
5. Lägg dina egna favoriter i `scanner_watchlist.txt` (Yahoo-tickers, t.ex. `INVE-B.ST`).

## Viktiga begränsningar (läs dessa)
- **Inte realtid.** Skannern körs var 5:e minut (GitHub kan försena), och Yahoo-data är inofficiell. I varje varning står vad Yahoo anger: **REALTID**, **FÖRDRÖJD (ca X min)** eller **OKÄND**. Norden är oftast fördröjd. Marknader som inte kan läsas märks **EJ TILLGÄNGLIG**, och de räknas aldrig som skannade.
- **Pre-market i USA** täcks bara delvis, eftersom screenern utgår från ordinarie handel. Lägg aktier du vill följa före öppning i `scanner_watchlist.txt`.
- **First North** går inte att skilja från huvudlistan i Yahoos screener, och småbolagstäckningen i Norden är ojämn.
- **Inte automatiserat**: SEC-filings, kassa och finansieringsbehov, historik över omvända splittar, handelsstopp samt blankningsdata. De står som OKÄND i stället för att gissas.
- **Nyheterna är rubriker**, inte verifierade fakta. Öppna länken och kolla källan innan du tror på något.
- **Poängen är en rangordning, inte en sannolikhet**, och vikterna är en tolkning av din prompt. Små, spekulativa bolag kan falla lika snabbt som de stiger, och du kan förlora hela insatsen. Det här är inga köp- eller säljrekommendationer.
