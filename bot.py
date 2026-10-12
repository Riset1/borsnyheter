#!/usr/bin/env python3
"""
BörstNyheter v2 – hämtar nyheter, filtrerar och postar till Discord via webhook.

Körs av GitHub Actions (se .github/workflows/nyheter.yml).
Testa lokalt utan att posta något:   DRY_RUN=1 python bot.py
"""
import hashlib
import html
import json
import os
import re
import sys
import time
from calendar import timegm
from datetime import datetime, timedelta, timezone

import feedparser
import requests

import config

UA = "Mozilla/5.0 (compatible; BorstNyheter/1.0; +https://github.com)"
SEEN_FILE = "seen.json"
STATE_FILE = "bot_state.json"
SEEN_MAX = 6000
DRY_RUN = os.getenv("DRY_RUN") == "1"

WEBHOOK = os.getenv("DISCORD_WEBHOOK", "").strip()
WEBHOOK_BOLAG = os.getenv("DISCORD_WEBHOOK_BOLAG", "").strip() or WEBHOOK
WEBHOOK_INVEST = os.getenv("DISCORD_WEBHOOK_INVEST", "").strip() or WEBHOOK
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip() or "gemini-2.5-flash"

# Inställningar (har standardvärden om din config.py är en äldre version)
AI_DAILY_LIMIT = getattr(config, "AI_DAILY_LIMIT", 60)
AI_MIN_INTERVAL_MIN = getattr(config, "AI_MIN_INTERVAL_MIN", 20)
AI_BATCH_MAX = getattr(config, "AI_BATCH_MAX", 20)
AI_WAIT_MAX_MIN = getattr(config, "AI_WAIT_MAX_MIN", 60)
SKIP_NEUTRAL_FOR = getattr(config, "SKIP_NEUTRAL_FOR", ["Bitcoin"])
SKIP_NEUTRAL_ALL = getattr(config, "SKIP_NEUTRAL_ALL", False)
CRYPTO_MAX_PER_RUN = getattr(config, "CRYPTO_MAX_PER_RUN", 2)
CRYPTO_WORDS = getattr(config, "CRYPTO_WORDS", config.TOPIC_WORDS.get("Bitcoin", []))
DEDUPE_HOURS = getattr(config, "DEDUPE_HOURS", 4)
CONCEPTS = getattr(config, "CONCEPTS", {})

# Guld (🟡) = extra bra nyhet. Titeln innehåller ett starkt ord, eller en positiv nyhet gäller ett bolag i bolag.txt.
GOLD_STRONG_WORDS = getattr(config, "GOLD_STRONG_WORDS", [
    "stororder", "ny order", "order på", "order värd", "tecknar order", "vinner order", "tilldelas",
    "förvärvar", "uppköp", "uppköpsbud", "bud på", "budet", "bjuds ut",
    "höjer prognos", "höjer riktkurs", "höjer målet", "rekordvinst", "rekordresultat", "överträffar",
    "godkänn", "genombrott", "licensavtal", "partnerskap",
    "raises guidance", "raises outlook", "raises forecast", "record profit", "record earnings",
    "beats estimates", "beats expectations", "wins contract", "awarded contract", "contract win",
    "fda approval", "fda approves", "approved by fda", "breakthrough", "acquires", "to acquire",
    "takeover bid", "buyout", "upgraded to buy", "short squeeze",
])
GOLD_FOR_WATCHLIST = getattr(config, "GOLD_FOR_WATCHLIST", True)

# ------------------------------------------------------------
#  INVESTERINGAR: nya investeringar från stora profiler, investerare, Trump, stater och fonder
#  Profiler läggs i profiler.txt. Allmänna flöden och ord kan ändras här eller i config.py.
# ------------------------------------------------------------
INVEST_VERBS = getattr(config, "INVEST_VERBS", [
    "stake", "invest", "buys", "bought", "buying", "acquir", "new position", "position in", "13f", "13d", "13g",
    "funding", "loan", "grant", "bailout", "subsid", "award", "backs", "backing", "sells", "sold", "dumps", "exits",
    "köper", "köpte", "investerar", "investering", "förvärv", "tar en post", "ökar", "minskar", "säljer", "lämnar",
    "andel i", "ägarandel", "storägare", "går in i", "satsar",
])
INVEST_POS = getattr(config, "INVEST_POS", [
    "takes stake", "new stake", "buys", "bought", "invests", "investing", "new position", "increases stake",
    "boosts stake", "adds to", "backs", "equity stake", "funding", "award", "köper", "köpte", "investerar", "satsar",
    "tar en post", "ökar sin", "ökar i", "går in i", "ägarandel",
])
INVEST_NEG = getattr(config, "INVEST_NEG", [
    "sells stake", "sold stake", "dumps", "exits", "cuts stake", "reduces stake", "trims", "dumped", "divests",
    "säljer", "sålde", "lämnar", "minskar", "avyttrar",
])
GOLD_FOR_PROFILES = getattr(config, "GOLD_FOR_PROFILES", True)
INVEST_FEEDS = getattr(config, "INVEST_FEEDS", [
    {"namn": "Stat/regering tar andel (USA)", "sprak": "en",
     "q": '"equity stake" ("U.S. government" OR "Trump administration" OR Pentagon OR "Department of Energy") when:1d'},
    {"namn": "Statliga satsningar (USA)", "sprak": "en",
     "q": '(Pentagon OR "Department of Energy" OR "Commerce Department" OR "CHIPS Act") (invests OR award OR loan OR stake OR funding) company when:1d'},
    {"namn": "Statsfonder", "sprak": "en",
     "q": '("sovereign wealth fund" OR "Public Investment Fund" OR Mubadala OR "Norges Bank Investment") (stake OR invests OR buys) when:1d'},
    {"namn": "Aktivister och nya poster", "sprak": "en",
     "q": '("13D" OR "13F" OR "new stake" OR "takes stake" OR "activist investor") when:1d'},
    {"namn": "Staten investerar (Sverige)", "sprak": "sv",
     "q": '(staten OR regeringen OR AP-fonden OR Riksgälden) (investerar OR köper OR "går in" OR ägarandel) bolag when:1d'},
    {"namn": "Storägare (Sverige)", "sprak": "sv",
     "q": '(storägare OR "köper aktier" OR "tar en post" OR "ökar i") (Wallenberg OR Investor OR Industrivärden OR Lundbergs) when:1d'},
])
PROFILES = []       # fylls i från profiler.txt när boten startar


# ---------------------------------------------------------------- hjälpfunktioner
def log(*a):
    print(*a, flush=True)


def now_utc():
    return datetime.now(timezone.utc)


def norm_words(text):
    return re.sub(r"[^a-z0-9åäö]+", " ", text.lower()).strip()


def keys_for(item):
    """Två nycklar per nyhet: länken och rubriken (fångar exakt samma nyhet från flera källor)."""
    k1 = "L" + hashlib.sha1(item["link"].encode()).hexdigest()[:16]
    k2 = "T" + hashlib.sha1(norm_words(item["title"])[:70].encode()).hexdigest()[:16]
    return k1, k2


def has_word(text, words):
    """Returnerar de ord ur listan som finns i texten (matchar ordets början)."""
    found = []
    for w in words:
        if re.search(r"(?<![a-zåäö0-9])" + re.escape(w.lower()), text):
            found.append(w)
    return found


def clean_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_seen():
    return load_json(SEEN_FILE, [])


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen[-SEEN_MAX:], f)


def load_state():
    st = load_json(STATE_FILE, {})
    if not isinstance(st, dict):
        st = {}
    ai = st.setdefault("ai", {})
    ai.setdefault("date", "")
    ai.setdefault("calls", 0)
    ai.setdefault("last_call", None)
    ai.setdefault("blocked_until", None)
    st.setdefault("recent", [])
    return st


def save_state(st):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)


def load_watch():
    """Läser bolag.txt (ett bolag per rad, # = kommentar)."""
    names = []
    try:
        with open("bolag.txt", encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if line:
                    names.append(line)
    except FileNotFoundError:
        pass
    return names[:30]


def load_profiles():
    """Läser profiler.txt. Format: 'Namn | alias | alias'. Lägg [sv] sist för svensk sökning. Max 25 rader."""
    out = []
    try:
        with open("profiler.txt", encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if not line:
                    continue
                sprak = "sv" if "[sv]" in line.lower() else "en"
                line = re.sub(r"\[sv\]", "", line, flags=re.I).strip()
                names = [n.strip() for n in line.split("|") if n.strip()]
                if names:
                    out.append({"names": names, "sprak": sprak})
    except FileNotFoundError:
        pass
    return out[:25]


# ---------------------------------------------------------------- hämtning
def build_feeds(watch):
    feeds = list(config.FEEDS)
    for name in watch:
        feeds.append({
            "namn": f"Bevakning: {name}",
            "url": config.gnews(f'"{name}" aktie OR stock OR shares when:1d', "sv"),
            "topic": "Bolag",
        })
    for f in INVEST_FEEDS:
        feeds.append({"namn": f"Invest: {f['namn']}", "url": config.gnews(f["q"], f["sprak"]),
                      "topic": "Investeringar", "kräver": INVEST_VERBS})
    for p in PROFILES:
        names = " OR ".join(f'"{n}"' for n in p["names"])
        q = f'({names}) (stake OR invests OR buys OR acquires OR "new position" OR investerar OR köper OR förvärvar) when:1d'
        feeds.append({"namn": f"Profil: {p['names'][0]}", "url": config.gnews(q, p["sprak"]),
                      "topic": "Investeringar", "kräver": INVEST_VERBS})
    return feeds


def fetch_feed(feed):
    headers = {"User-Agent": UA}
    if "sec.gov" in feed["url"]:
        headers["User-Agent"] = "BorstNyheter/1.0 privat-nyhetsbot"
    r = requests.get(feed["url"], headers=headers, timeout=20)
    r.raise_for_status()
    parsed = feedparser.parse(r.content)
    items = []
    for e in parsed.entries:
        title = clean_html(e.get("title", ""))
        link = e.get("link", "")
        if not title or not link:
            continue
        src_name = feed["namn"]
        src = e.get("source")
        if src and src.get("title"):
            src_name = src["title"]
            if title.endswith(" - " + src_name):          # Google News lägger på källan
                title = title[: -len(src_name) - 3]
        summary = clean_html(e.get("summary", ""))
        if "news.google.com" in feed["url"]:               # Google News-sammanfattning är bara skräp
            summary = ""
        pub = None
        pp = e.get("published_parsed") or e.get("updated_parsed")
        if pp:
            pub = datetime.fromtimestamp(timegm(pp), tz=timezone.utc)
        items.append({"title": title, "link": link, "summary": summary,
                      "source": src_name, "published": pub, "feed": feed})
    return items


# ---------------------------------------------------------------- klassificering
def classify(item, watch):
    """Returnerar (kategori, sentiment, info) eller (None, None, None) om nyheten inte är intressant.
    info = vilka ord som låg bakom bedömningen (används för förklaringen utan AI)."""
    feed = item["feed"]
    text = (item["title"] + " " + item["summary"]).lower()
    watch_hits = [w for w in watch if has_word(text, [w])]

    if feed.get("bara_bevakade") and not watch_hits:
        return None, None, None
    if feed.get("kräver") and not has_word(text, feed["kräver"]):
        return None, None, None                      # inga investeringsord = ingen investeringsnyhet

    category = feed.get("topic")
    if not category:
        if watch_hits:
            category = "Bolag"
        else:
            for topic, words in config.TOPIC_WORDS.items():
                if has_word(text, words):
                    category = topic
                    break
            if not category and (has_word(text, config.EVENT_WORDS) or has_word(text, GOLD_STRONG_WORDS)):
                category = "Bolag"
            if not category and has_word(text, config.MACRO_WORDS):
                category = "Allmänt"
    if not category:
        return None, None, None

    title = item["title"].lower()
    pos_t, neg_t = has_word(title, config.POSITIVE_WORDS), has_word(title, config.NEGATIVE_WORDS)
    pos_s, neg_s = has_word(text, config.POSITIVE_WORDS), has_word(text, config.NEGATIVE_WORDS)
    gold_t = has_word(title, GOLD_STRONG_WORDS)          # starka ord räknas alltid som positiva
    pos_t = pos_t + [w for w in gold_t if w not in pos_t]
    pos = 2 * len(pos_t) + len(pos_s)
    neg = 2 * len(neg_t) + len(neg_s)
    if category == "Investeringar":                  # stora investerare som köper = positivt, säljer = negativt
        ip, ineg = has_word(title, INVEST_POS), has_word(title, INVEST_NEG)
        pos_t += [w for w in ip if w not in pos_t]
        neg_t += [w for w in ineg if w not in neg_t]
        pos += 2 * len(ip)
        neg += 2 * len(ineg)
    sentiment = "positiv" if pos > neg else "negativ" if neg > pos else "neutral"
    prof = [n for p in PROFILES for n in p["names"] if has_word(text, [n])][:2]
    info = {"pos": sorted(set(pos_t + pos_s)), "neg": sorted(set(neg_t + neg_s)), "watch": watch_hits, "profiles": prof,
            "events": has_word(text, config.EVENT_WORDS)[:3], "macro": has_word(text, config.MACRO_WORDS)[:3]}
    return category, sentiment, info


def gold_reason(it):
    """Returnerar en kort motivering om nyheten är extra bra (guld), annars None.
    Gäller bara positiva nyheter, aldrig krypto och aldrig 'gamla nyheter'."""
    if it["sent"] != "positiv" or it.get("crypto") or it.get("old"):
        return None
    if GOLD_FOR_PROFILES and it["cat"] == "Investeringar" and it["info"].get("profiles"):
        return f"stor investerare går in: {it['info']['profiles'][0]}"
    hits = has_word(it["title"].lower(), GOLD_STRONG_WORDS)
    if hits:
        return f"starkt ord i rubriken: {hits[0]}"
    if GOLD_FOR_WATCHLIST and it["info"]["watch"]:
        return f"positiv nyhet om bevakat bolag: {it['info']['watch'][0]}"
    return None


def is_crypto(item):
    if item["feed"].get("topic") == "Bitcoin":
        return True
    return bool(has_word(item["title"].lower(), CRYPTO_WORDS))


# ---------------------------------------------------------------- dubblettkoll (utan AI)
_STOP = set("the an of to in on for and or at by with from is are was be as after over new says say "
            "och att det som en ett på av för med till är har efter om".split())
_GENERIC_CAPS = {"the", "why", "how", "what", "this", "new", "breaking", "here", "stock", "stocks", "shares",
                 "market", "markets", "aktie", "aktien", "börsen", "nyheter", "news", "live", "update"}


def _tokens(title):
    return {w for w in re.findall(r"[a-zåäö0-9]+", title.lower()) if len(w) > 2 and w not in _STOP}


def _fingerprint(title):
    """Språkoberoende avtryck: siffror, egennamn (versaler) och begrepp."""
    toks = set()
    for n in re.findall(r"\d+(?:[.,]\d+)?", title):
        toks.add("#" + n.replace(",", "."))
    for w in re.findall(r"[A-ZÅÄÖ][A-Za-zÅÄÖåäö0-9&]+", title):
        lw = w.lower()
        if len(lw) >= 3 and lw not in _GENERIC_CAPS:
            toks.add("@" + lw)
    low = title.lower()
    for concept, words in CONCEPTS.items():
        if has_word(low, words):
            toks.add("~" + concept)
    return toks


def same_story(t1, t2):
    """Gissar om två rubriker handlar om samma händelse, även på olika språk."""
    l1, l2 = t1.lower(), t2.lower()
    up1, dn1 = bool(has_word(l1, config.POSITIVE_WORDS)), bool(has_word(l1, config.NEGATIVE_WORDS))
    up2, dn2 = bool(has_word(l2, config.POSITIVE_WORDS)), bool(has_word(l2, config.NEGATIVE_WORDS))
    if (up1 and not dn1 and dn2 and not up2) or (dn1 and not up1 and up2 and not dn2):
        return False                                   # motsatta riktningar = olika nyheter
    a, b = _tokens(t1), _tokens(t2)
    if a and b and len(a & b) / len(a | b) >= 0.6:
        return True
    fa, fb = _fingerprint(t1), _fingerprint(t2)
    if fa and fb:
        common = fa & fb
        has_num = any(t.startswith("#") for t in common)
        ratio = len(common) / min(len(fa), len(fb))
        if ratio >= 0.6 and (len(common) >= 3 or (len(common) >= 2 and has_num)):
            return True
    return False


def dedupe_candidates(cands, recent):
    """Tar bort dubbletter inom körningen och mot nyligen skickade. Returnerar (behållna, borttagna)."""
    kept, dropped = [], []
    for it in cands:
        if any(r["c"] == it["cat"] and same_story(it["title"], r["t"]) for r in recent):
            dropped.append(it)
            continue
        dup = next((k for k in kept if k["cat"] == it["cat"] and same_story(it["title"], k["title"])), None)
        if dup is None:
            kept.append(it)
        elif len(it["summary"]) > len(dup["summary"]):          # behåll den med mest information
            kept[kept.index(dup)] = it
            dropped.append(dup)
        else:
            dropped.append(it)
    return kept, dropped


# ---------------------------------------------------------------- AI (Gemini), en förfrågan per körning
def ai_status(st, n_items):
    """Avgör om AI får användas i den här körningen. Returnerar ('ja'|'senare'|'idag_slut', orsak)."""
    if not GEMINI_KEY:
        return "av", "ingen GEMINI_API_KEY"
    ai, now = st["ai"], now_utc()
    today = now.strftime("%Y-%m-%d")
    if ai["date"] != today:
        ai["date"], ai["calls"] = today, 0
    if ai["calls"] >= AI_DAILY_LIMIT:
        return "idag_slut", f"dagsgränsen på {AI_DAILY_LIMIT} anrop är nådd"
    if ai["blocked_until"]:
        until = datetime.fromisoformat(ai["blocked_until"])
        if until > now:
            mins = (until - now).total_seconds() / 60
            return ("senare" if mins <= AI_WAIT_MAX_MIN else "idag_slut"), f"pausad av Google i {mins:.0f} min till"
    if ai["last_call"]:
        since = (now - datetime.fromisoformat(ai["last_call"])).total_seconds() / 60
        if since < AI_MIN_INTERVAL_MIN - 2:
            return "senare", f"senaste AI-anropet var för {since:.0f} min sedan"
    return "ja", ""


def ai_batch(items, recent_titles):
    """Skickar alla nyheter i en förfrågan. Returnerar (lista med svar | None, felorsak, dagskvot_slut)."""
    lines = []
    for i, it in enumerate(items):
        lines.append(f"[{i}] ({it['cat']}) {it['title']} | {it['summary'][:250]} | källa: {it['source']}")
    recent_txt = "\n".join("- " + t for t in recent_titles[:40]) or "(inga)"
    prompt = (
        "Du är analytiker åt en svensk småsparare som handlar på svenska och amerikanska börsen. "
        "Nedan finns numrerade nyheter (källor på olika språk) och en lista över nyheter som redan skickats.\n"
        "Svara ENBART med en JSON-lista med ett objekt per nyhet, i exakt detta format:\n"
        '[{"i": 0, "relevant": true, "sentiment": "positiv", '
        '"sammanfattning": "1-2 meningar på svenska", '
        '"varfor": "1-2 meningar på svenska om varför nyheten är bra/dålig för börsen och på vilket sätt", '
        '"berorda": "vilka bolag, branscher eller marknader som gynnas (+) eller missgynnas (-)", '
        '"gammal": false, "dublett_av": null}]\n\n'
        "Regler:\n"
        "- relevant=false för brus, reklam, ren åsikt, kändisnyheter eller sådant som inte påverkar börsen.\n"
        "- sentiment ska vara \"positiv\", \"negativ\" eller \"neutral\" ur ett börsperspektiv för de berörda "
        "bolagen/marknaderna. Använd neutral bara om nyheten verkligen inte är tydligt bra eller dålig.\n"
        "- berorda: nämn konkreta bolag (med ticker om du är säker), branscher eller marknader, till exempel "
        "\"Gynnar: Equinor, oljebolag. Missgynnar: flygbolag.\" Hitta aldrig på bolag. Skriv \"OKÄNT\" om det är oklart.\n"
        "- gammal=true om marknaden sannolikt redan har rört sig och nyheten är inprisad.\n"
        "- dublett_av: om nyheten handlar om samma händelse som en annan nyhet i listan (även på annat språk), "
        "ange numret på den BÄSTA av dem hos de övriga (ange inte dublett på båda). Om den redan finns bland "
        "redan skickade nyheter, skriv \"redan_skickad\". Annars null.\n"
        "- Skriv allt på svenska. Använd bara det som står i rubriken och texten, gissa inga fakta.\n\n"
        f"REDAN SKICKADE:\n{recent_txt}\n\nNYHETER:\n" + "\n".join(lines)
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2,
                                 "maxOutputTokens": 8192}}
    try:
        r = requests.post(url, json=body, headers={"x-goog-api-key": GEMINI_KEY}, timeout=90)
    except Exception as ex:
        return None, f"nätverksfel: {ex}", False, None
    if r.status_code == 429:
        txt = r.text.lower()
        retry = None
        m = re.search(r'"retrydelay":\s*"(\d+)', txt.replace(" ", ""))
        if m:
            retry = int(m.group(1))
        return None, "429 (gränsen nådd)", ("perday" in txt.replace(" ", "") or "per day" in txt), retry
    if r.status_code >= 400:
        return None, f"HTTP {r.status_code}: {r.text[:200]}", False, None
    try:
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        txt = txt[txt.index("["): txt.rindex("]") + 1]
        data = json.loads(txt)
        if not isinstance(data, list):
            raise ValueError("inte en lista")
        return data, None, False, None
    except Exception as ex:
        return None, f"kunde inte tolka AI-svaret ({ex})", False, None


def register_ai_call(st, err, day_quota_out, retry_s):
    ai, now = st["ai"], now_utc()
    ai["calls"] += 1
    ai["last_call"] = now.isoformat()
    if err and err.startswith("HTTP 4"):          # felaktig nyckel/modell: försök inte igen på 2 timmar
        ai["blocked_until"] = (now + timedelta(hours=2)).isoformat()
    if err and "429" in err:
        if day_quota_out:                       # Googles dygnskvot nollställs vid midnatt Pacific (~08:00 UTC)
            nxt = now.replace(hour=8, minute=5, second=0, microsecond=0)
            if nxt <= now:
                nxt += timedelta(days=1)
            ai["blocked_until"] = nxt.isoformat()
        else:
            ai["blocked_until"] = (now + timedelta(seconds=max(retry_s or 0, 600))).isoformat()


# ---------------------------------------------------------------- Discord
def fallback_explain(it):
    """Förklaring utan AI: bygger på vilka ord som utlöste bedömningen. Mindre exakt än AI."""
    info, sent, cat = it["info"], it["sent"], it["cat"]
    words = info["pos"] if sent == "positiv" else info["neg"] if sent == "negativ" else []
    if sent == "neutral":
        why = "Ingen tydlig riktning i rubriken (automatisk bedömning utan AI)."
    else:
        why = f"Rubriken tyder på en {sent} nyhet (nyckelord: {', '.join(words[:4])}). Automatisk bedömning utan AI."
    if it.get("gold"):
        why += f" Extra bra: {it['gold']}."
    touched = [cat] + info.get("profiles", []) + info["watch"] + info["events"] + info["macro"]
    return why, ", ".join(dict.fromkeys(touched)) + " (gissning från nyckelord)"


def post_discord(webhook, it):
    sent = it["sent"]
    icon = {"positiv": "🟢", "negativ": "🔴"}.get(sent, "⚪")
    color = {"positiv": 0x2ECC71, "negativ": 0xE74C3C}.get(sent, 0x95A5A6)
    title = f"{icon} {it['title']}"
    if it.get("gold"):
        icon, color = "🟡", 0xF1C40F
        title = f"🟡 {it['title']}"
    if it.get("old"):
        title = f"🔴 Gamla nyheter 🔴 {it['title']}"
        color = 0x992D22
    fields = []
    if it.get("varfor"):
        fields.append({"name": "Varför", "value": it["varfor"][:500], "inline": False})
    if it.get("berorda"):
        fields.append({"name": "Berör", "value": it["berorda"][:500], "inline": False})
    embed = {
        "title": title[:256],
        "url": it["link"],
        "description": (it.get("ai_summary") or it["summary"])[:350],
        "color": color,
        "fields": fields,
        "footer": {"text": f"{it['cat']} • {it['source']} • {'AI' if it.get('via_ai') else 'nyckelord'}"},
    }
    if it["published"]:
        embed["timestamp"] = it["published"].isoformat()
    payload = {"username": "BörstNyheter", "embeds": [embed]}

    if DRY_RUN:
        log(f"[DRY] {it['cat']:8} {sent:8} {'AI ' if it.get('via_ai') else 'KW '} {it['title'][:80]}")
        for f in fields:
            log(f"        {f['name']}: {f['value'][:140]}")
        return True

    for _ in range(3):
        r = requests.post(webhook, json=payload, timeout=20)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
            continue
        if r.status_code >= 400:
            log(f"  Discord-fel {r.status_code}: {r.text[:200]}")
            return False
        time.sleep(1)
        return True
    return False


# ---------------------------------------------------------------- huvudprogram
def main():
    if not DRY_RUN and not WEBHOOK:
        log("FEL: Hemligheten DISCORD_WEBHOOK saknas. Se README.md, steg 4.")
        sys.exit(1)

    now = now_utc()
    PROFILES[:] = load_profiles()
    watch = load_watch()
    seen = load_seen()
    seen_set = set(seen)
    state = load_state()
    cutoff = now - timedelta(hours=config.MAX_AGE_HOURS)
    recent_cut = now - timedelta(hours=DEDUPE_HOURS)
    state["recent"] = [r for r in state["recent"] if datetime.fromisoformat(r["ts"]) > recent_cut]

    # 1. Hämta
    all_items = []
    for feed in build_feeds(watch):
        try:
            got = fetch_feed(feed)
            log(f"OK   {feed['namn']}: {len(got)} st")
            all_items += got
        except Exception as ex:
            log(f"SKIP {feed['namn']}: {ex}")

    # 2. Filtrera bort gamla, redan sedda och exakta dubbletter
    fresh, run_keys = [], set()
    for it in all_items:
        if it["published"] and it["published"] < cutoff:
            continue
        k1, k2 = keys_for(it)
        if k1 in seen_set or k2 in seen_set or k1 in run_keys or k2 in run_keys:
            continue
        run_keys.update((k1, k2))
        it["keys"] = (k1, k2)
        fresh.append(it)

    # 3. Klassificera
    candidates = []
    for it in fresh:
        cat, sent, info = classify(it, watch)
        if cat is None:
            seen += list(it["keys"])           # ointressant, kom ihåg så vi slipper kolla igen
            continue
        it["cat"], it["sent"], it["info"], it["crypto"] = cat, sent, info, is_crypto(it)
        candidates.append(it)

    # Nyast först
    candidates.sort(key=lambda x: x["published"] or now, reverse=True)

    # 4. Dubbletter mellan källor och språk (regelbaserat)
    candidates, dropped = dedupe_candidates(candidates, state["recent"])
    for it in dropped:
        seen += list(it["keys"])
    if dropped:
        log(f"Dubbletter borttagna: {len(dropped)}")

    # 5. AI-steg: ett enda anrop för hela omgången
    status, reason = ai_status(state, len(candidates))
    ai_by_item = {}
    ai_ok = False
    if candidates and status == "ja":
        batch = candidates[:AI_BATCH_MAX]
        data, err, day_out, retry_s = ai_batch(batch, [r["t"] for r in state["recent"]])
        register_ai_call(state, err, day_out, retry_s)
        if data is None:
            log(f"AI misslyckades: {err}")
            permanent = err.startswith("HTTP 4")
            status, reason = ("idag_slut" if (day_out or permanent) else "senare"), err
            if permanent:
                log("  -> Kontrollera GEMINI_API_KEY och GEMINI_MODEL. Nyheterna skickas med nyckelordsfilter tills vidare.")
        else:
            ai_ok = True
            for res in data:
                if isinstance(res, dict) and isinstance(res.get("i"), int) and 0 <= res["i"] < len(batch):
                    ai_by_item[res["i"]] = res
            status, reason = "senare", "resten väntar på nästa AI-anrop"
            log(f"AI: {len(ai_by_item)} av {len(batch)} nyheter bedömda (anrop {state['ai']['calls']} idag)")
            for i, it in enumerate(batch):
                res = ai_by_item.get(i)
                if res:
                    it["_ai"] = res
    elif candidates:
        log(f"AI används inte nu: {reason}")

    # 6. Bestäm vad som ska postas
    to_post, wait_count = [], 0
    for i, it in enumerate(candidates):
        res = it.get("_ai")
        if ai_ok and res is not None:
            if res.get("relevant") is False:
                seen += list(it["keys"])
                continue
            dub = res.get("dublett_av")
            if dub == "redan_skickad":
                seen += list(it["keys"])
                continue
            if isinstance(dub, int) and 0 <= dub < len(candidates) and dub != i and candidates[dub].get("_ai") \
                    and candidates[dub]["_ai"].get("dublett_av") != i and candidates[dub]["_ai"].get("relevant") is not False:
                seen += list(it["keys"])
                continue
            it["ai_summary"] = res.get("sammanfattning") or None
            it["varfor"] = res.get("varfor") or None
            ber = res.get("berorda")
            it["berorda"] = None if not ber or str(ber).strip().upper() == "OKÄNT" else str(ber)
            if res.get("sentiment") in ("positiv", "negativ", "neutral"):
                it["sent"] = res["sentiment"]
            it["old"] = bool(res.get("gammal"))
            it["gold"] = gold_reason(it)
            it["via_ai"] = True
        else:
            # Ingen AI för den här nyheten. Vänta på AI om det går, annars skicka med nyckelordsfilter.
            age_min = ((now - it["published"]).total_seconds() / 60) if it["published"] else 9999
            if GEMINI_KEY and status == "senare" and age_min < AI_WAIT_MAX_MIN:
                wait_count += 1
                continue                                 # inte markerad som sedd, tas om nästa körning
            it["gold"] = gold_reason(it)
            it["varfor"], it["berorda"] = fallback_explain(it)
            it["via_ai"] = False
        to_post.append(it)
    if wait_count:
        log(f"{wait_count} nyheter väntar på nästa AI-anrop")

    # 7. Mindre brus: neutral krypto, neutrala kategorier och kryptotak
    final, crypto_n = [], 0
    for it in to_post:
        neutral = it["sent"] == "neutral"
        if neutral and (SKIP_NEUTRAL_ALL or it["cat"] in SKIP_NEUTRAL_FOR or it["cat"] == "Investeringar"
                        or (it["crypto"] and "Bitcoin" in SKIP_NEUTRAL_FOR)):
            seen += list(it["keys"])
            continue
        if it["crypto"]:
            if crypto_n >= CRYPTO_MAX_PER_RUN:
                seen += list(it["keys"])
                continue
            crypto_n += 1
        final.append(it)

    final = final[: config.MAX_POSTS_PER_RUN]
    # Vanliga nyheter först (äldst först), gamla nyheter sist
    final.sort(key=lambda x: (bool(x.get("old")), x["published"] or now))

    # 8. Posta
    posted = 0
    for it in final:
        hook = WEBHOOK_BOLAG if it["cat"] == "Bolag" else WEBHOOK_INVEST if it["cat"] == "Investeringar" else WEBHOOK
        if post_discord(hook, it):
            posted += 1
            seen += list(it["keys"])
            state["recent"].append({"t": it["title"], "c": it["cat"], "ts": now.isoformat()})

    state["recent"] = state["recent"][-80:]
    log(f"Klart: {len(all_items)} hämtade, {len(fresh)} nya, {len(candidates)} efter dubblettkoll, {posted} postade.")
    if not DRY_RUN:
        save_seen(seen)
        save_state(state)


if __name__ == "__main__":
    main()
