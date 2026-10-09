# ============================================================
#  Spike-skanner – inställningar
#  Här justerar du filter, marknader och poänggränser.
# ============================================================

# Skicka bara varning om signalpoängen är minst så här hög (0-100)
MIN_SCORE = 65

# En aktie som redan rusat (REDAN RUSAT) varnar vi bara för om poängen är minst så här hög
MIN_SCORE_ALREADY_RUSHED = 85

# Så här länge (minuter) väntar vi innan samma aktie varnas igen
# (om inte poängen stigit minst 10 steg eller den nått UTBROTT PÅGÅR)
COOLDOWN_MIN = 60

# Max antal varningar per körning
MAX_ALERTS_PER_RUN = 8

# Hur många kandidater per marknad som analyseras på minutdata
MAX_CANDIDATES_PER_MARKET = 15

# Hur många aktier Yahoo-screenern hämtar per marknad innan vi väljer ut kandidater
SCREEN_SIZE = 40

# Dagens kursförändring (%) för tidiga rörelser (prompten: +2 % till +20 %).
# Vi tillåter högre så att aktier som redan rusat kan flaggas som REDAN RUSAT.
MIN_CHANGE = 2
MAX_CHANGE = 80

# Hoppa över aktier där senaste minutstapeln är äldre än så här (minuter) = ingen aktuell handel
MAX_STALE_MIN = 30

# Spread (köp/sälj) över detta räknas som risk
SPREAD_RISK_PCT = 5.0

# Antal handelsdagar bakåt som jämförs för tidsjusterad relativ volym (RVOL)
RVOL_LOOKBACK_DAYS = 4

# ------------------------------------------------------------
#  MARKNADER
#  open/close = när vi skannar (lokal tid, inkl. pre-market i USA)
#  min_turnover / good_turnover = omsättning i lokal valuta (kurs x volym)
# ------------------------------------------------------------
MARKETS = {
    "USA": {
        "tz": "America/New_York", "open": (4, 0), "close": (20, 0), "currency": "USD",
        "exchanges": ["NMS", "NYQ", "ASE", "NCM", "NGM"],
        "price": (0.5, 20), "mcap_max": 300_000_000, "min_dayvolume": 100_000,
        "min_turnover": 100_000, "good_turnover": 250_000,
    },
    "Sverige": {
        "tz": "Europe/Stockholm", "open": (8, 45), "close": (17, 45), "currency": "SEK",
        "exchanges": ["STO"], "min_dayvolume": 20_000,
        "min_turnover": 500_000, "good_turnover": 1_500_000,
    },
    "Norge": {
        "tz": "Europe/Oslo", "open": (8, 45), "close": (16, 30), "currency": "NOK",
        "exchanges": ["OSL"], "min_dayvolume": 20_000,
        "min_turnover": 500_000, "good_turnover": 1_500_000,
    },
    "Danmark": {
        "tz": "Europe/Copenhagen", "open": (8, 45), "close": (17, 15), "currency": "DKK",
        "exchanges": ["CPH"], "min_dayvolume": 10_000,
        "min_turnover": 350_000, "good_turnover": 1_000_000,
    },
    "Finland": {
        "tz": "Europe/Helsinki", "open": (9, 45), "close": (18, 45), "currency": "EUR",
        "exchanges": ["HEL"], "min_dayvolume": 10_000,
        "min_turnover": 50_000, "good_turnover": 150_000,
    },
}

# Vilken marknad en ticker i scanner_watchlist.txt tillhör (efter ticker-ändelse)
SUFFIX_TO_MARKET = {".ST": "Sverige", ".OL": "Norge", ".CO": "Danmark", ".HE": "Finland"}

# ------------------------------------------------------------
#  NYHETER OCH RISK (ord matchar början av ord)
# ------------------------------------------------------------
# Starka katalysatorer
STRONG_CATALYST_WORDS = [
    "contract", "order", "partnership", "agreement", "fda", "approval", "approves", "clearance",
    "acquisition", "acquire", "merger", "buyout", "patent", "award", "grant", "license", "licens",
    "breakthrough", "trial results", "phase 3", "phase 2", "guidance", "record revenue",
    "avtal", "kontrakt", "förvärv", "partnerskap", "godkänn", "patent", "uppköp", "bud på",
    "stororder", "licensavtal", "genombrott",
]

# Tecken på utspädning/finansieringsrisk i nyhetsrubriker
DILUTION_WORDS = [
    "offering", "warrant", "convertible", "registered direct", "private placement",
    "at-the-market", "atm program", "shelf registration", "reverse split", "dilut",
    "going concern", "nyemission", "riktad emission", "företrädesemission", "teckningsoption",
    "konvertibel", "emission", "kapitalanskaffning",
]
