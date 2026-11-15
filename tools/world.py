#!/usr/bin/env python3
"""Posturile din toată lumea (în afară de România, care are lista ei) din Radio Browser:
câte un fișier pe țară, dist/v1/c/<cc>.json, și dist/v1/top.json — cele mai ascultate din lume, pentru „Surpriză”.

    python3 tools/world.py      # citește data/raw/rb-all.json (tools/fetch.py)

Aici nu se verifică fiecare flux (sunt zeci de mii): Radio Browser le verifică el, zilnic, și dă doar ce merge."""
import hashlib, json, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import curate, geo

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "dist", "v1", "c")
MAX_PER_COUNTRY = 1500  # SUA au ~7.000; peste 1.500 sunt mai ales dubluri și fluxuri de test
TOP, TOP_PER_COUNTRY = 600, 30
norm = geo.norm

# genurile din aplicație; câteva reguli altfel decât la noi („popular” în spaniolă nu e muzică populară)
WORLD_RX = dict(curate.GENRE_RE)
WORLD_RX.pop("manele", None)
WORLD_RX.pop("maghiar", None)
WORLD_RX["populara"] = re.compile(r"\bfolk|folklor|folclor|traditional|ethnic|celtic|volksmusik|ranchera|norte[ñn]", re.I)
WORLD_RX["latin"] = re.compile(r"\blatin|salsa|reggaeton|bachata|cumbia|merengue|tropical|bossa|samba|sertanejo", re.I)
WORLD_RX["country"] = re.compile(r"\bcountry\b|bluegrass|americana", re.I)
EXTRA_GENRES = [("latin", "Latino", "Latin"), ("country", "Country", "Country")]
EN = {"pop": "Pop & hits", "dance": "Dance & electronic", "rock": "Rock & alternative", "manele": "Manele & party",
      "populara": "Folk & traditional", "oldies": "Retro & oldies", "jazz": "Jazz, blues & soul", "clasica": "Classical",
      "chill": "Chill & lounge", "hiphop": "Hip-hop & urban", "stiri": "News & talk", "crestin": "Christian",
      "maghiar": "Hungarian", "copii": "Kids", "colinde": "Christmas"}
VAGUE = re.compile(r"^(music|misc|various|local|local radio|entertainment|regional|live|online radio|radio|internet radio|fm)$", re.I)
EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-➿️‍]")
JUNK = re.compile(r"\s*[\(\[][^\)\]]*\b(?:\d+\s*k(?:bps)?|aac\+?|mp3|ogg|hq|lq|low|high|mobile|https?|stream)\b[^\)\]]*[\)\]]\s*"
                  r"|\s+\d{2,3}\s?k(?:bps)?\b|\s*[|/\-–]?\s*\b(?:aac\+?|mp3|ogg|opus|hq|lq)\s*$", re.I)
# unele posturi își umflă voturile (sute de mii): contează mai ales ascultările din ultima zi
VOTES_CAP, CLICKS_CAP = 5000, 5000


def genres(tags, name):
    text = " ".join(t for t in tags if not VAGUE.match(t)) + " | " + name
    return [k for k, rx in WORLD_RX.items() if rx.search(text)][:3]


def clean(name):
    n = EMOJI.sub(" ", name or "")
    for _ in range(3):  # „… | MP3 128k”: întâi pleacă „128k”, apoi „| MP3”
        n = JUNK.sub(" ", n).strip()
    n = re.sub(r"\s+", " ", n).strip(" -|·•_.,")
    return n[:60].strip()


def key(n):
    k = re.sub(r"\b(radio|the)\b", " ", norm(n))
    return re.sub(r"\s+", "", k)


def fmt_of(st):
    c = (st.get("codec") or "").upper()
    if st.get("hls") == 1 or (st.get("url_resolved") or "").lower().split("?")[0].endswith(".m3u8"):
        return "hls"
    return {"MP3": "mp3", "AAC": "aac", "AAC+": "aac", "OGG": "ogg"}.get(c)


def score(st):
    br = st.get("bitrate") or 0
    url = st.get("url_resolved") or st.get("url") or ""
    sc = min(st.get("votes", 0), VOTES_CAP) ** 0.5 + min(st.get("clickcount", 0), CLICKS_CAP) ** 0.5 * 4
    sc += 10 if 64 <= br <= 192 else 4 if br > 192 else 0
    sc += 3 if url.startswith("https") else 0
    sc -= 30 if ("token" in url or "zt=" in url) else 0
    return sc


def build(rb):
    by_cc = defaultdict(list)
    for st in rb:
        cc = (st.get("countrycode") or "").upper()
        if not re.fullmatch(r"[A-Z]{2}", cc) or cc == "RO" or st.get("lastcheckok") != 1:
            continue
        url = st.get("url_resolved") or st.get("url") or ""
        f = fmt_of(st)
        n = clean(st.get("name"))
        if not url.startswith("http") or not f or len(n) < 2:
            continue
        by_cc[cc].append((st, url, f, n))

    countries, files = [], {}
    for cc, items in by_cc.items():
        groups = defaultdict(list)
        for it in items:
            groups[key(it[3]) or it[3]].append(it)
        best = []
        seen_url = set()
        for k, g in groups.items():
            g.sort(key=lambda it: -score(it[0]))
            st, url, f, n = g[0]
            if url in seen_url:
                continue
            seen_url.add(url)
            alts = [u for u in dict.fromkeys(it[1] for it in g[1:]) if u != url][:2]
            tags = [t.strip() for t in (st.get("tags") or "").split(",") if t.strip()]
            pop = min(sum(it[0].get("votes", 0) for it in g), VOTES_CAP) + 10 * min(sum(it[0].get("clickcount", 0) for it in g), CLICKS_CAP)
            s = {"id": None, "n": n, "t": "w", "cc": cc, "u": url}
            if alts:
                s["u2"] = alts
            gs = genres(tags, n)
            if gs:
                s["g"] = gs
            s["fmt"] = f
            if 0 < (st.get("bitrate") or 0) < 1000:
                s["br"] = st["bitrate"]
            region = (st.get("state") or "").strip()
            if region and norm(region) != norm(st.get("country") or ""):
                s["r"] = region[:40]
            if st.get("geo_lat") and st.get("geo_long"):
                s["lat"], s["lon"] = round(st["geo_lat"], 4), round(st["geo_long"], 4)
            fav = st.get("favicon") or ""
            if fav.startswith("http"):
                s["logo"] = fav
            web = st.get("homepage") or ""
            if web.startswith("http"):
                s["web"] = web
            s["pop"] = pop
            s["_score"] = score(st) + pop ** 0.5
            best.append(s)
        best.sort(key=lambda s: -s["_score"])
        best = best[:MAX_PER_COUNTRY]
        ids = set()
        for s in best:
            base = "w-" + cc.lower() + "-" + (curate.slug(s["n"]) or "post")
            sid, i = base, 2
            while sid in ids:
                sid, i = f"{base}-{i}", i + 1
            ids.add(sid)
            s["id"] = sid
            del s["_score"]
        name = items[0][0].get("country") or cc
        geo_pts = sorted((s["lat"], s["lon"]) for s in best if "lat" in s)
        entry = {"cc": cc, "n": name, "k": len(best)}
        if len(geo_pts) >= 3:
            lats = sorted(p[0] for p in geo_pts)
            lons = sorted(p[1] for p in geo_pts)
            entry["lat"], entry["lon"] = lats[len(lats) // 2], lons[len(lons) // 2]
        countries.append(entry)
        files[cc] = best
    return countries, files


def top(files):
    pool = []
    for cc, ss in files.items():
        pool += sorted(ss, key=lambda s: -s["pop"])[:TOP_PER_COUNTRY]
    return sorted(pool, key=lambda s: -s["pop"])[:TOP]


def dump(path, doc):
    data = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    old = open(path, "rb").read() if os.path.exists(path) else None
    if old != data:
        with open(path + ".tmp", "wb") as f:
            f.write(data)
        os.replace(path + ".tmp", path)
    return hashlib.sha1(data).hexdigest()[:10], len(data)


def genre_list():
    out = [{"k": k, "n": n, "en": EN.get(k, n)} for k, n, _ in curate.GENRES]
    out += [{"k": k, "n": n, "en": en} for k, n, en in EXTRA_GENRES]
    return out


def main():
    rb = json.load(open(os.path.join(ROOT, "data", "raw", "rb-all.json")))
    countries, files = build(rb)
    if sum(c["k"] for c in countries) < 15000:
        raise SystemExit("prea puține posturi în lume — nu suprascriu fișierele")
    for c in countries:
        c["h"], c["b"] = dump(os.path.join(OUT, c["cc"].lower() + ".json"), {"v": 2, "country": c["cc"], "stations": files[c["cc"]]})
    keep = {c["cc"].lower() + ".json" for c in countries}
    for f in os.listdir(OUT):
        if f.endswith(".json") and f not in keep:
            os.remove(os.path.join(OUT, f))
    t = top(files)
    th, tb = dump(os.path.join(ROOT, "dist", "v1", "top.json"), {"v": 2, "stations": t})
    countries.sort(key=lambda c: c["cc"])
    print(f"lume: {len(countries)} țări, {sum(c['k'] for c in countries)} posturi, top {len(t)}")
    return countries, {"h": th, "b": tb, "k": len(t)}


if __name__ == "__main__":
    main()
