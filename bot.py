#!/usr/bin/env python3
"""
BörstNyheter – hämtar nyheter, filtrerar och postar till Discord via webhook.

Körs av GitHub Actions var 10:e minut (se .github/workflows/nyheter.yml).
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
SEEN_MAX = 6000
DRY_RUN = os.getenv("DRY_RUN") == "1"

WEBHOOK = os.getenv("DISCORD_WEBHOOK", "").strip()
WEBHOOK_BOLAG = os.getenv("DISCORD_WEBHOOK_BOLAG", "").strip() or WEBHOOK
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip() or "gemini-2.5-flash"


# ---------------------------------------------------------------- hjälpfunktioner
def log(*a):
    print(*a, flush=True)


def norm_words(text):
    return re.sub(r"[^a-z0-9åäö]+", " ", text.lower()).strip()


def keys_for(item):
    """Två nycklar per nyhet: länken och rubriken (fångar samma nyhet från flera källor)."""
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


def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen[-SEEN_MAX:], f)


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


# ---------------------------------------------------------------- hämtning
def build_feeds(watch):
    feeds = list(config.FEEDS)
    for name in watch:
        feeds.append({
            "namn": f"Bevakning: {name}",
            "url": config.gnews(f'"{name}" aktie OR stock OR shares when:1d', "sv"),
            "topic": "Bolag",
        })
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
    """Returnerar (kategori, sentiment) eller (None, None) om nyheten inte är intressant."""
    feed = item["feed"]
    text = (item["title"] + " " + item["summary"]).lower()
    watch_hits = [w for w in watch if has_word(text, [w])]

    if feed.get("bara_bevakade") and not watch_hits:
        return None, None

    category = feed.get("topic")
    if not category:
        if watch_hits:
            category = "Bolag"
        else:
            for topic, words in config.TOPIC_WORDS.items():
                if has_word(text, words):
                    category = topic
                    break
            if not category and has_word(text, config.EVENT_WORDS):
                category = "Bolag"
            if not category and has_word(text, config.MACRO_WORDS):
                category = "Allmänt"
    if not category:
        return None, None

    title = item["title"].lower()
    pos = 2 * len(has_word(title, config.POSITIVE_WORDS)) + len(has_word(text, config.POSITIVE_WORDS))
    neg = 2 * len(has_word(title, config.NEGATIVE_WORDS)) + len(has_word(text, config.NEGATIVE_WORDS))
    sentiment = "positiv" if pos > neg else "negativ" if neg > pos else "neutral"
    return category, sentiment


# ---------------------------------------------------------------- valfritt AI-filter (Gemini, gratis nivå)
def ai_enrich(item, category):
    """Ber Gemini bedöma nyheten och skriva en kort svensk sammanfattning. Returnerar dict eller None."""
    prompt = (
        "Du hjälper en svensk småsparare som handlar på svenska och amerikanska börsen. "
        "Bedöm nyheten nedan. Svara ENBART med JSON med dessa fält:\n"
        '{"relevant": true/false, "sentiment": "positiv"|"negativ"|"neutral", '
        '"sammanfattning": "1-2 meningar på svenska", "gammal": true/false}\n'
        "relevant=false om nyheten är brus, reklam, åsikter utan nyhetsvärde eller inte påverkar börsen. "
        "gammal=true om nyheten sannolikt redan är inprisad (marknaden har redan rört sig).\n\n"
        f"Kategori: {category}\nRubrik: {item['title']}\nText: {item['summary'][:600]}\nKälla: {item['source']}"
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    try:
        r = requests.post(url, json=body, headers={"x-goog-api-key": GEMINI_KEY}, timeout=30)
        r.raise_for_status()
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
        return json.loads(txt)
    except Exception as ex:  # AI är bara en bonus – om det strular skickar vi nyheten ändå
        log(f"  (AI hoppades över: {ex})")
        return None


# ---------------------------------------------------------------- Discord
def post_discord(webhook, item, category, sentiment, summary, old=False):
    icon = {"positiv": "🟢", "negativ": "🔴"}.get(sentiment, "⚪")
    color = {"positiv": 0x2ECC71, "negativ": 0xE74C3C}.get(sentiment, 0x95A5A6)
    title = f"{icon} {item['title']}"
    if old:
        title = f"🔴 Gamla nyheter 🔴 {item['title']}"
        color = 0x992D22
    embed = {
        "title": title[:256],
        "url": item["link"],
        "description": summary[:350],
        "color": color,
        "footer": {"text": f"{category} • {item['source']}"},
    }
    if item["published"]:
        embed["timestamp"] = item["published"].isoformat()
    payload = {"username": "BörstNyheter", "embeds": [embed]}

    if DRY_RUN:
        log(f"[DRY] {category:8} {sentiment:8} {item['title'][:90]}  <{item['source']}>")
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

    watch = load_watch()
    seen = load_seen()
    seen_set = set(seen)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.MAX_AGE_HOURS)

    # 1. Hämta
    all_items = []
    for feed in build_feeds(watch):
        try:
            got = fetch_feed(feed)
            log(f"OK   {feed['namn']}: {len(got)} st")
            all_items += got
        except Exception as ex:
            log(f"SKIP {feed['namn']}: {ex}")

    # 2. Filtrera bort gamla, redan sedda och dubbletter
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
        cat, sent = classify(it, watch)
        if cat is None:
            seen += list(it["keys"])           # ointressant – kom ihåg så vi slipper kolla igen
            continue
        it["cat"], it["sent"] = cat, sent
        candidates.append(it)

    # Nyast först, begränsa antal
    candidates.sort(key=lambda x: x["published"] or datetime.now(timezone.utc), reverse=True)
    batch = candidates[: config.MAX_POSTS_PER_RUN]
    batch.sort(key=lambda x: x["published"] or datetime.now(timezone.utc))   # posta äldst först

    # 4. AI + posta
    ai_calls, posted = 0, 0
    for it in batch:
        summary, sent, old = it["summary"][:300], it["sent"], False
        if GEMINI_KEY and ai_calls < config.MAX_AI_CALLS:
            ai_calls += 1
            res = ai_enrich(it, it["cat"])
            time.sleep(4)                        # håll oss under gratisgränsen per minut
            if res:
                if res.get("relevant") is False:
                    seen += list(it["keys"])
                    continue
                summary = res.get("sammanfattning") or summary
                sent = res.get("sentiment") if res.get("sentiment") in ("positiv", "negativ", "neutral") else sent
                old = bool(res.get("gammal"))
        hook = WEBHOOK_BOLAG if it["cat"] == "Bolag" else WEBHOOK
        if post_discord(hook, it, it["cat"], sent, summary, old):
            posted += 1
            seen += list(it["keys"])

    log(f"Klart: {len(all_items)} hämtade, {len(fresh)} nya, {len(candidates)} intressanta, {posted} postade.")
    if not DRY_RUN:
        save_seen(seen)


if __name__ == "__main__":
    main()
