# ============================================================
#  BörstNyheter – inställningar
#  Här ändrar du källor och nyckelord. Du behöver inte röra bot.py.
# ============================================================

# Hur gamla nyheter får vara (timmar). Äldre nyheter hoppas över.
MAX_AGE_HOURS = 3

# Max antal meddelanden per körning (skyddar mot att Discord blir översvämmat)
MAX_POSTS_PER_RUN = 15

# Max antal AI-anrop per körning (bara om du lagt in GEMINI_API_KEY)
MAX_AI_CALLS = 12


def gnews(query, sprak="sv"):
    """Bygger en Google News RSS-adress av en sökfråga."""
    from urllib.parse import quote
    if sprak == "sv":
        return f"https://news.google.com/rss/search?q={quote(query)}&hl=sv&gl=SE&ceid=SE:sv"
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"


# ------------------------------------------------------------
#  KÄLLOR
#  topic         = tvinga kategori (Olja, Guld, Bitcoin ...) – annars avgör nyckelorden
#  bara_bevakade = skicka bara om en bolag från bolag.txt nämns
# ------------------------------------------------------------
FEEDS = [
    # --- Svenska källor (via Google News, så vi slipper betalväggar och trasiga RSS) ---
    {"namn": "Dagens Industri", "url": gnews("site:di.se when:1d")},
    {"namn": "Placera",         "url": gnews("site:placera.se when:1d")},
    {"namn": "Affärsvärlden",   "url": gnews("site:affarsvarlden.se when:1d")},
    {"namn": "Börsen Sverige",  "url": gnews("Stockholmsbörsen OR OMXS30 OR börsen when:1d")},
    {"namn": "Pressmeddelanden", "url": gnews("pressmeddelande bolagsstämma OR delårsrapport OR förvärv when:1d")},

    # --- Amerikanska / internationella källor ---
    {"namn": "Yahoo Finance",   "url": "https://finance.yahoo.com/news/rssindex"},
    {"namn": "CNBC",            "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
    {"namn": "MarketWatch",     "url": "https://feeds.marketwatch.com/marketwatch/topstories/"},
    {"namn": "Reuters",         "url": gnews("site:reuters.com markets OR business when:1d", "en")},
    {"namn": "Bloomberg",       "url": gnews("site:bloomberg.com markets when:1d", "en")},

    # --- Ämnen ---
    {"namn": "Olja",    "url": gnews("olja OR oljepris OR \"oil price\" OR OPEC when:1d", "en"), "topic": "Olja"},
    {"namn": "Guld",    "url": gnews("guld OR guldpris OR \"gold price\" when:1d", "en"),       "topic": "Guld"},
    {"namn": "Bitcoin", "url": gnews("bitcoin OR krypto OR \"crypto market\" when:1d", "en"),   "topic": "Bitcoin"},

    # --- Amerikanska bolagsrapporter (visas bara för bolag i bolag.txt) ---
    {"namn": "SEC 8-K",
     "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom",
     "bara_bevakade": True},

    # --- Sociala medier (Reddit blockerar ibland GitHubs servrar, då hoppas de över) ---
    {"namn": "Reddit r/wallstreetbets", "url": "https://www.reddit.com/r/wallstreetbets/top/.rss?t=hour"},
    {"namn": "Reddit r/stocks",         "url": "https://www.reddit.com/r/stocks/top/.rss?t=hour"},
]

# ------------------------------------------------------------
#  NYCKELORD (matchar början av ord, så "rapport" tar även "rapporten")
# ------------------------------------------------------------

# Händelser som ofta rör enskilda bolag -> kategori "Bolag"
EVENT_WORDS = [
    "vinstvarning", "profit warning", "delårsrapport", "bokslut", "rapport", "earnings",
    "förvärv", "köper", "acquires", "acquisition", "merger", "fusion", "bud på", "takeover",
    "riktkurs", "price target", "upgrade", "downgrade", "varnar för", "warns",
    "emission", "nyemission", "offering", "split", "utdelning", "dividend", "återköp", "buyback",
    "insynsköp", "insider", "stämma", "ceo", "vd ", "avgår", "resigns", "konkurs", "bankrupt",
    "order", "kontrakt", "contract", "godkänn", "approval", "fda", "lawsuit", "stämning",
    "utredning", "investigation", "ipo", "notering", "avnotering", "guidance", "prognos",
]

# Stora världshändelser och makro -> kategori "Allmänt"
MACRO_WORDS = [
    "ränta", "räntebesked", "riksbanken", "fed ", "federal reserve", "ecb", "inflation", "kpi",
    "recession", "arbetslöshet", "bnp", "gdp", "tullar", "tariff", "sanktion", "sanction",
    "krig", "war", "attack", "missil", "houthi", "iran", "ryssland", "russia", "ukraina", "ukraine",
    "israel", "gaza", "kina", "china", "taiwan", "val ", "election", "president", "statsminister",
    "regering", "nedstängning", "shutdown", "bankkris", "banking crisis", "kraschar", "crash",
    "rally", "börsras", "sell-off", "selloff", "opec", "energikris", "handelskrig", "trade war",
]

# Ämnesord -> kategori
TOPIC_WORDS = {
    "Olja":    ["olja", "oljepris", "oil", "brent", "opec", "crude"],
    "Guld":    ["guld", "gold", "bullion"],
    "Bitcoin": ["bitcoin", "btc", "krypto", "crypto", "ethereum"],
}

# Sentiment: ord som tyder på bra eller dåliga nyheter
POSITIVE_WORDS = [
    "höjer", "stiger", "rusar", "rekord", "förvärvar", "ökar", "överträffar", "starkare", "vinst",
    "order", "kontrakt", "godkänn", "uppgradera", "köprekommendation", "återhämtning", "lyfter",
    "beat", "surge", "jump", "soar", "rally", "record", "upgrade", "raises", "wins", "approval",
    "growth", "profit", "gains", "strong", "boost", "outperform", "buyback", "dividend",
]
NEGATIVE_WORDS = [
    "faller", "rasar", "sänker", "vinstvarning", "varnar", "minskar", "förlust", "svagare",
    "konkurs", "nedgång", "recession", "krasch", "kraschar", "nedgradera", "säljrekommendation",
    "plunge", "falls", "drops", "downgrade", "cuts", "warns", "miss", "lawsuit", "investigation",
    "bankrupt", "loss", "slump", "sell-off", "selloff", "crash", "weak", "fraud", "halted",
]
