# BörstNyheter – gratis nyhetsbot för Discord

Boten hämtar nyheter från svenska och amerikanska källor (plus Reddit), filtrerar bort brus och postar det intressanta i din Discord. Den körs gratis av GitHub Actions var 10:e minut. Ingen server behövs.

## Vad du behöver
- Ett Discord-konto med en egen server (där du är admin)
- Ett gratis GitHub-konto (github.com)
- Ca 15 minuter

---

## Steg 1 – Skapa en webhook i Discord
1. Öppna din Discord-server. Skapa gärna två textkanaler: `#nyheter` (allmänt, olja, guld, bitcoin) och `#bolagsnyheter`.
2. Högerklicka på kanalen `#nyheter` → **Redigera kanal** → **Integrationer** → **Webhooks** → **Ny webhook**.
3. Klicka på webhooken → **Kopiera webhook-URL**. Spara den tillfälligt i ett anteckningsblock. **Dela den aldrig med någon**, den fungerar som ett lösenord.
4. (Valfritt) Gör samma sak för `#bolagsnyheter` och spara den URL:en separat.

## Steg 2 – Skapa ett repo på GitHub
1. Logga in på github.com → klicka **+** uppe till höger → **New repository**.
2. Namn: `borsnyheter`.
3. Välj **Public**. Det är viktigt, eftersom publika repon får obegränsad gratis körtid. Dina hemliga nycklar syns inte, de läggs i steg 4.
4. Kryssa inte i några extra rutor, låt allt vara tomt. Klicka **Create repository**.

## Steg 3 – Ladda upp filerna
1. Packa upp zip-filen `borsnyheter.zip` på din dator.
2. I ditt nya repo: klicka **uploading an existing file** (eller **Add file → Upload files**).
3. Dra in **allt innehåll** från den uppackade mappen: `bot.py`, `config.py`, `bolag.txt`, `requirements.txt`, `seen.json`, `README.md`, `scanner.py`, `scanner_config.py`, `scanner_watchlist.txt`, `scanner_state.json`, `signals_log.json` **och mappen `.github`** (med två filer: `nyheter.yml` och `scanner.yml`). Om GitHub bara accepterar en fil åt gången i mappen `.github`, skapa dem en och en enligt nästa punkt.
   - Mappen `.github` kan vara dold. På Windows: Visa → Visa → Dolda objekt. På Mac: Cmd + Shift + punkt.
   - Om GitHub inte tar med mappen `.github` vid uppladdning: klicka **Add file → Create new file**, skriv `.github/workflows/nyheter.yml` som filnamn (snedstrecken skapar mapparna), klistra in innehållet från filen `nyheter.yml` och klicka **Commit changes**. Gör samma sak för `.github/workflows/scanner.yml`.
4. Klicka **Commit changes**.

## Steg 4 – Lägg in hemligheterna
1. I repot: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
2. Skapa:
   - Name: `DISCORD_WEBHOOK`, Secret: webhook-URL:en från steg 1.
   - (Valfritt) Name: `DISCORD_WEBHOOK_BOLAG`, Secret: URL:en för `#bolagsnyheter`. Om du hoppar över den hamnar allt i samma kanal.
   - (Valfritt) Name: `DISCORD_WEBHOOK_SCANNER`, URL:en för en egen kanal `#spike-skanner`. Hoppar du över den hamnar skannerns varningar i samma kanal som `DISCORD_WEBHOOK`.
   - (Valfritt) Name: `GEMINI_API_KEY`, se steg 7.

## Steg 5 – Ge Actions rätt att spara
1. **Settings** → **Actions** → **General**.
2. Scrolla ner till **Workflow permissions** → välj **Read and write permissions** → **Save**.

## Steg 6 – Starta och testa
1. Klicka på fliken **Actions**. Om GitHub frågar, klicka **I understand my workflows, enable them**.
2. Välj **BörstNyheter** i listan till vänster → **Run workflow** → **Run workflow**.
3. Vänta ca 1 minut, klicka på körningen och på **run**. Du ser loggen. Rader som `OK Yahoo Finance: 30 st` betyder att källan funkar. `SKIP` betyder att en källa inte gick att nå just nu (vanligt för Reddit), vilket inte är farligt.
4. Kolla Discord. De första nyheterna ska dyka upp. Därefter körs det automatiskt var 10:e minut.

## Steg 7 – (Valfritt) Gratis AI för bättre filter och svenska sammanfattningar
1. Gå till aistudio.google.com och logga in med ett Google-konto.
2. Klicka **Get API key** → skapa en nyckel → kopiera den.
3. Lägg in den som secret `GEMINI_API_KEY` (steg 4).
4. Då skriver Gemini en kort svensk sammanfattning, sorterar bort onödigt brus och flaggar nyheter där marknaden sannolikt redan rört sig (de får rubriken "🔴 Gamla nyheter 🔴").
5. Om AI-delen slutar fungera kan modellnamnet ha bytts ut hos Google. Lägg då in en secret `GEMINI_MODEL` med ett aktuellt modellnamn från aistudio.google.com. Boten postar nyheter ändå, även om AI-delen failar.

---

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

## Viktigt
- Detta är inga köp- eller säljrekommendationer. Rykten från sociala medier kan vara pumpningar.
- Repot är publikt: dela aldrig webhook-URL:er eller API-nycklar i koden eller i chatten. Lägg dem bara som Secrets.

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
