#!/usr/bin/env python3
"""Face assets/stations.json din Radio Browser (data/raw/rb-ro.json) + verificarea fluxurilor
(data/raw/check.json) + corecturile mele (data/overrides.json).

    python3 -I tools/curate.py          # scrie lista și data/review.txt (de citit de om)
"""
import json, os, re, sys, unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import geo

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "data", "raw")
norm = geo.norm

# ---------- posturi naționale (rețele cu frecvențe în multe județe) ----------
NATIONAL = [
    # nume afișat, nume RB normalizate, gen
    ("Radio România Actualități", {"radio romania actualitati", "romania actualitati"}, ["stiri", "pop"]),
    ("Antena Satelor", {"antena satelor", "radio antena satelor", "romania antena satelor"}, ["populara", "stiri"]),
    ("Radio România Cultural", {"radio romania cultural", "romania cultural"}, ["stiri", "clasica"]),
    ("Radio România Muzical", {"radio romania muzical"}, ["clasica"]),
    ("Radio România Internațional", {"radio romania international", "romania international 1"}, ["stiri"]),
    ("Kiss FM", {"kiss fm", "kiss fm ro", "kiss fm 107 9"}, ["pop", "dance"]),
    ("Magic FM", {"magic fm", "magic fm romania"}, ["oldies", "pop"]),
    ("Rock FM", {"rock fm", "rockfm", "rock fm romania"}, ["rock"]),
    ("Radio ZU", {"radio zu", "zu radio", "radio zu!"}, ["pop", "dance"]),
    ("Europa FM", {"europa fm", "europafm", "europa fm romania", "europa fm aac"}, ["pop", "stiri"]),
    ("Digi FM", {"digi fm", "digifm"}, ["pop", "stiri"]),
    ("Digi24 FM", {"digi24 fm", "digi24fm"}, ["stiri"]),
    ("Pro FM", {"pro fm", "profm"}, ["pop"]),
    ("Virgin Radio", {"virgin radio romania"}, ["pop", "hiphop"]),
    ("Radio Guerrilla", {"radio guerrilla", "radio guerilla"}, ["rock"]),
    ("Radio Trinitas", {"radio trinitas", "radio trinitas 88 5", "trinitas radio"}, ["crestin"]),
    ("Radio Maria", {"radio maria", "radio maria romania"}, ["crestin"]),
    ("Național FM", {"national fm", "nationa fm"}, ["populara", "pop"]),
    ("Gold FM", {"goldfm", "radio gold fm", "gold fm 96 9", "gold fm"}, ["oldies"]),
    ("Romantic FM", {"romantic fm"}, ["oldies"]),
    ("Smart FM", {"smart fm", "smart radio"}, ["oldies"]),
    ("RFI România", {"rfi romania"}, ["stiri", "pop"]),
    ("Realitatea FM", {"realitatea fm"}, ["stiri"]),
    ("Radio Impuls", {"radio impuls romania", "radio impuls"}, ["pop"]),
    ("Dance FM", {"dance fm", "dance fm 89 5 bucharest", "dancefmromania"}, ["dance"]),
    ("Radio Itsy Bitsy", {"itsy bitsy", "itsybitsy"}, ["copii"]),
    ("Sport Total FM", {"sport total fm spt fm"}, ["stiri"]),
    ("Vibe FM", {"vibe fm"}, ["pop"]),
]
NAT_BY_KEY = {k: (name, g) for name, keys, g in NATIONAL for k in keys}

# ---------- genuri ----------
GENRES = [
    ("pop", "Pop & hituri", r"\bpop\b|top ?40|top hits|\bhits?\b|\bchr\b|adult contemporary|contemporary|hit music|fresh|\bhot ac\b"),
    ("dance", "Dance & electronic", r"dance|house|\bedm\b|electro|club|techno|trance|minimal|drum and bass|dnb|jungle|breakbeat|dubstep|rave"),
    ("rock", "Rock & alternativ", r"rock|metal|alternative|\bindie\b|grunge|punk"),
    ("manele", "Manele & petrecere", r"manele|mamele|petrecere|\bmixta\b"),
    ("populara", "Populară & folclor", r"popular|folclor|\betno\b|lautar|traditional|romanian folk|muzica populara"),
    ("oldies", "Retro & oldies", r"oldies|retro|\b[5-9]0'?s\b|\b[5-9]0's|decades|\bgold|nostalg|slagare|classic hits|eurodisco|italo|disco|goldies|romantic"),
    ("jazz", "Jazz, blues & soul", r"jazz|blues|\bsoul\b|funk|r'?n'?b|swing"),
    ("clasica", "Clasică", r"classical|\bclasic\b|opera|symphon|baroque|orchestral|clasica"),
    ("chill", "Chill & lounge", r"chill|lounge|ambient|relax|lo-?fi|downtempo|smooth|cafe"),
    ("hiphop", "Hip-hop & urban", r"hip ?-?hop|\brap\b|trap|urban|gangsta"),
    ("stiri", "Știri & talk", r"\bnews\b|\btalk\b|stiri|știri|information|cultural|dezbateri|politi"),
    ("crestin", "Creștine", r"christian|crestin|creștin|religi|ortodox|orthodox|catholic|catolic|evangel|worship|gospel|bisericesc|biblie|bible|predici|aventist"),
    ("maghiar", "Maghiare", r"hungarian|maghiar|magyar|unguresc|\brádió\b"),
    ("copii", "Copii", r"\bkids\b|copii"),
    ("colinde", "Colinde", r"christmas|colinde|xmas"),
]
GENRE_RE = [(k, re.compile(rx, re.I)) for k, _, rx in GENRES]
# taguri prea vagi ca să spună ceva
VAGUE = re.compile(r"^(music|muzica|misc|various|romania|romanian|local|local radio|local news|news talk music|entertainment|regional|live|online radio)$", re.I)


def genres_of(tags, name):
    name = re.sub(r"clasic radio", "", name, flags=re.I)  # marcă, nu gen
    text = " ".join(t for t in tags if not VAGUE.match(t.strip())) + " | " + name
    out = []
    for k, rx in GENRE_RE:
        if rx.search(text):
            out.append(k)
    # „folk” din Radio Browser înseamnă de obicei folclor românesc
    if "populara" not in out and re.search(r"\bfolk\b", text, re.I) and not re.search(r"indie folk|folk rock|folk bun", text, re.I):
        out.append("populara")
    if "manele" in out and "populara" in out and "petrecere" in text.lower() and "manele" not in text.lower():
        out.remove("manele")
    if "rock" in out and "pop rock" in text.lower() and len(out) > 2:
        out.remove("rock")
    return out[:3]


# ---------- nume: „Post -Oraș 99,8 FM” → (post, oraș, frecvență) ----------
FREQ = re.compile(r"(?<![\d.,])(8[7-9]|9\d|10[0-8])(?:[.,](\d)\s*(?:fm|mhz)?|\s*(?:fm|mhz)\b)(?![\d])", re.I)
AM = re.compile(r"\b(\d{3,4})\s*AM\b", re.I)
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")


def split_name(raw):
    s = EMOJI.sub(" ", raw).replace(" ", " ")
    s = re.sub(r"\s+", " ", s).strip()
    freq = None
    m = FREQ.search(s)
    if m:
        freq = f"{m.group(1)}.{m.group(2) or 0}"
    elif AM.search(s):
        freq = AM.search(s).group(1) + " AM"
    city = None
    name = s
    # „Nume (📌 Oraș 📡 89,3 FM)”
    m = re.match(r"^(.*?)\s*\(\s*(.+?)\s+(?:\d.*)?\)\s*$", s)
    if m and "(" in s and freq:
        name, city = m.group(1), m.group(2)
    else:
        # „Nume -Oraș 99,8 FM”, „Nume -stația Oraș 99.8 FM”, „Nume - Oraș 94,1 FM”
        m = (re.match(r"^(.+?)\s+-\s*(.+)$", s) or re.match(r"^(.+?)\s-(\S.*)$", s)
             or re.match(r"^(.+?)\s+((?:stația|statia)\s+.+)$", s, re.I))
        if m:
            name, rest = m.group(1), m.group(2)
            rest = re.sub(r"^(stația|statia|stația|statia)\s+", "", rest, flags=re.I)
            rest = FREQ.sub("", rest)
            rest = re.sub(r"\b(fm|mhz|dab|\d{3,4}\s*am)\b", "", rest, flags=re.I)
            rest = re.sub(r"\s+\b[A-Z]{2}\b\s*$", "", rest.strip())  # „Darabani BT”
            city = rest.strip(" ,-()") or None
    name = FREQ.sub("", name)
    name = re.sub(r"\b(fm)\s+\1\b", r"\1", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip(" -_,")
    return name, city, freq


def place_for(city, hint=None, near=None):
    if not city:
        return None
    p = geo.geocode(city, hint, near)
    if p:
        return p
    for part in re.split(r"[/,]|\s{2,}| și | si |-(?=[A-ZȘȚĂÂÎ])", city):
        words = part.split()
        # „Leordeni Arges” → „Leordeni”
        for k in range(len(words), 0, -1):
            cand = " ".join(words[:k])
            if len(cand) < 3:
                break
            p = geo.geocode(cand, hint, near)
            if p:
                return p
    return None


SMALL = {"fm", "am", "rve", "dj", "ai", "hd", "ubb", "umf", "usv", "rfi", "mfm", "gfm", "ebs", "xfm", "ok", "ltu", "spt", "cfm", "zc", "fx"}


def prettify(name):
    """„VIVA FM” → „Viva FM”, păstrând siglele scurte."""
    def w(x):
        lo = x.lower()
        if lo in SMALL:
            return x.upper()
        if x.isupper() and len(x) > 3 and "." not in x:
            return x.capitalize()
        return x
    name = re.sub(r"^(Radio)(?=[A-Z])", r"\1 ", name.replace("_", " "))  # „RadioDoamna”
    return " ".join(w(x) for x in name.split())


def town_in_name(name, near=None):
    """„Radio HIT Iasi” → Iași; „Radio Prahova” → reședința Prahovei. Doar orașe/comune, nu sate."""
    words = re.sub(r"[^\w\s-]", " ", name).split()
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            cand = " ".join(words[i:i + n])
            if len(cand) < 4 or norm(cand) in ("radio", "romania", "fm", "dance", "music", "manele"):
                continue
            c = geo.county_by_name(cand)
            if c:
                seat = next(x for x in geo.COUNTIES if x[0] == c)[2]
                p = geo.geocode(seat, c)
            else:
                l = geo.places().get(geo.ALIAS.get(norm(cand), norm(cand)))
                p = l[0] if l else None
                if p and not (p[4] >= 5000 or norm(p[0]) == norm(cand) and p[4] > 0 or geo.is_town(p)):
                    p = None
            if p and (not near or geo.dist(near, (p[1], p[2])) < 60):
                return p
    return None


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")[:40]


def stream_score(st, chk):
    """Cât de bun e un flux pentru telefon: merge, are titluri, nu e uriaș, nu expiră."""
    if chk.get("code") != 200 or chk.get("fmt") not in ("mp3", "aac", "ogg", "hls"):
        return -1
    url = chk.get("final") or chk["url"]
    sc = 100
    if chk.get("metaint"):
        sc += 40
    if chk.get("fmt") == "hls":
        sc -= 30
    if "zt=" in url or "token" in url:  # adrese cu jeton care expiră
        sc -= 60
    try:
        br = int(re.sub(r"\D", "", str(chk.get("br") or st.get("bitrate") or 0)) or 0)
    except ValueError:
        br = 0
    if 64 <= br <= 192:
        sc += 15
    elif br > 192:
        sc += 5
    if url.startswith("https"):
        sc += 5
    sc += min(st.get("votes", 0), 20000) ** 0.5 / 10
    return sc


def main():
    doc, stations = build()
    json.dump(doc, open(os.path.join(ROOT, "assets", "stations.json"), "w"), ensure_ascii=False, separators=(",", ":"))


def build():
    rb = json.load(open(os.path.join(RAW, "rb-ro.json")))
    chk = json.load(open(os.path.join(RAW, "check.json")))
    ov = json.load(open(os.path.join(ROOT, "data", "overrides.json")))
    drop = [re.compile(x, re.I) for x in ov.get("drop", [])]
    rules = [(re.compile(k, re.I), v) for k, v in ov.get("rules", {}).items()]

    cands = []
    for st in rb:
        c = chk.get(st["stationuuid"], {})
        score = stream_score(st, c)
        if score < 0:
            continue
        raw = st["name"].strip()
        if any(rx.search(raw) for rx in drop):
            continue
        name, city, freq = split_name(raw)
        tags = [t.strip() for t in (st.get("tags") or "").split(",") if t.strip()]
        rec = {
            "raw": raw, "name": name, "city": city, "freq": freq, "tags": tags,
            "state": (st.get("state") or "").strip(), "lat": st.get("geo_lat"), "lon": st.get("geo_long"),
            "url": c.get("final") or c["url"], "fmt": c.get("fmt"), "meta": 1 if c.get("metaint") else 0,
            "br": c.get("br") or str(st.get("bitrate") or ""), "logo": st.get("favicon") or "", "web": st.get("homepage") or "",
            "votes": st.get("votes", 0), "score": score, "type": None, "county": None, "genres": None,
        }
        nk = norm(name)
        if nk in NAT_BY_KEY:
            rec["name"], rec["genres"] = NAT_BY_KEY[nk]
            rec["type"], rec["city"], rec["freq"] = "n", None, None
        for rx, v in rules:
            if rx.search(raw):
                rec.update(v)
                if "city" in v:
                    rec["lat"] = rec["lon"] = None  # orașul din corectură bate punctul din Radio Browser
        if rec.get("skip"):
            continue
        cands.append(rec)

    # localizare + tip
    for r in cands:
        if r["type"] == "n":
            continue
        hint = r.get("county")
        if not hint and r["state"]:
            hint = geo.county_by_name(r["state"])
        near = (r["lat"], r["lon"]) if r["lat"] else None
        p = place_for(r["city"], hint, near) if r["city"] else None
        if not p and r["state"] and not geo.county_by_name(r["state"]):
            p = place_for(r["state"], hint, near)  # „Câmpina”, „Timisoara” — nu județul
        if not p:
            p = town_in_name(r["name"], near)
        if p:
            r["city"], r["lat"], r["lon"] = p[0], p[1], p[2]
            r["county"] = r.get("county") or p[3] or geo.county_at(p[1], p[2])
        elif r["lat"] and geo.county_at(r["lat"], r["lon"]):
            t = geo.nearest(r["lat"], r["lon"])
            r["city"] = t[0] if t else None
            if t:
                r["lat"], r["lon"] = t[1], t[2]
            r["county"] = r.get("county") or (t[3] if t else None) or geo.county_at(r["lat"], r["lon"])
        else:
            r["city"] = None
            if hint:
                r["county"] = hint
        if r["county"] and not r["lat"]:
            seat = next(c for c in geo.COUNTIES if c[0] == r["county"])[2]
            p = geo.geocode(seat, r["county"])
            r["lat"], r["lon"] = p[1], p[2]
            r["city"] = r["city"] or p[0]
        if not r["type"]:
            local = bool(r["freq"]) or any(t.lower() == "local radio" for t in r["tags"])
            r["type"] = "l" if local and r["county"] else "o"
        if r["genres"] is None:
            r["genres"] = genres_of(r["tags"], r["name"])

    # dubluri: același nume + același loc, sau aceeași frecvență în același oraș
    groups = defaultdict(list)
    for r in cands:
        if r["type"] == "n":
            key = ("n", norm(r["name"]))
        elif r["type"] == "l":
            key = ("l", r["county"], r["freq"] or norm(r["name"]))
        else:
            key = ("o", norm(r["name"]))
        groups[key].append(r)
    # local fără frecvență + același nume cu frecvență în același județ → unul singur
    for key in [k for k in groups if k[0] == "l" and not FREQ.match(k[2] or "")]:
        for k2 in list(groups):
            if k2 != key and k2[0] == "l" and k2[1] == key[1] and k2 in groups and key in groups \
                    and any(norm(r["name"]) == key[2] for r in groups[k2]):
                groups[k2] += groups.pop(key)
                break
    def distinctive(ts):
        return any(t not in ("fm", "radio", "romania", "online", "live", "hits", "the") and not geo.places().get(t) for t in ts)

    def tokens(n):
        return frozenset(norm(n).replace("radio", " ").replace("radi", " ").split())

    local_by = defaultdict(list)
    for k, rs in groups.items():
        if k[0] == "l":
            local_by[k[1]].append(k)
    for k in [k for k in groups if k[0] == "o"]:
        rs = groups[k]
        c = rs[0].get("county")
        tk = tokens(rs[0]["name"])
        for lk in (local_by.get(c, []) if c else [x for l in local_by.values() for x in l]):
            ltk = tokens(groups[lk][0]["name"])
            small = tk if len(tk) <= len(ltk) else ltk
            # „Radio Cluj” ⊂ „Radio Ascor … din Cluj-Napoca” nu înseamnă același post: partea comună trebuie să fie un nume, nu un oraș
            if tk and ltk and (tk == ltk or (tk <= ltk or ltk <= tk) and distinctive(small)):
                for r in rs:
                    r["score"] -= 50  # fluxul local rămâne primul
                groups[lk] += groups.pop(k)
                break
    # online: același flux cu nume diferite → unul singur
    out = []
    seen_url = {}
    for key, rs in groups.items():
        rs.sort(key=lambda r: -r["score"])
        best = dict(rs[0])
        # numele cel mai „curat” din grup (cu diacritice, fără majuscule urlate)
        # numele fluxului ales; dintre variantele lui (aceleași litere) pe cea cu diacritice și fără majuscule urlate
        same = [r["name"] for r in rs if norm(r["name"]) == norm(best["name"])]
        names = sorted(set(same), key=lambda n: (n.isupper(), -sum(ch in "ăâîșțşţ" for ch in n.lower())))
        best["name"] = best["name"] if best["type"] == "n" else prettify(names[0])
        if not best.get("county"):
            o = next((r for r in rs if r.get("county")), None)
            if o:
                best.update(county=o["county"], city=o["city"], lat=o["lat"], lon=o["lon"])
        if not best.get("city"):
            best["city"] = next((r["city"] for r in rs if r.get("city")), None)
        best["alt"] = [u for u in dict.fromkeys(r["url"] for r in rs) if u != best["url"]][:2]
        best["votes"] = sum(r["votes"] for r in rs)
        for r in rs:
            if not best["logo"] and r["logo"]:
                best["logo"] = r["logo"]
            if not best["web"] and r["web"]:
                best["web"] = r["web"]
            if not best["genres"] and r["genres"]:
                best["genres"] = r["genres"]
            if not best.get("freq") and r.get("freq"):
                best["freq"] = r["freq"]
        if best["type"] == "o" and best["url"] in seen_url:
            other = seen_url[best["url"]]
            other["votes"] += best["votes"]
            continue
        seen_url.setdefault(best["url"], best)
        out.append(best)

    # id-uri stabile
    ids = set()
    stations = []
    for r in sorted(out, key=lambda r: ({"n": 0, "l": 1, "o": 2}[r["type"]], norm(r["name"]))):
        base = slug(r["name"] + ("-" + r["city"] if r["type"] == "l" and r["city"] else ""))
        sid, i = base, 2
        while sid in ids:
            sid, i = f"{base}-{i}", i + 1
        ids.add(sid)
        s = {"id": sid, "n": r["name"], "t": r["type"], "u": r["url"]}
        if r["alt"]:
            s["u2"] = r["alt"]
        if r["county"] and r["type"] != "n":
            s["c"] = r["county"]
        if r["city"] and r["type"] != "n":
            s["city"] = r["city"]
        if r.get("freq"):
            s["f"] = r["freq"]
        if r["lat"] and r["type"] != "n":
            s["lat"], s["lon"] = round(r["lat"], 4), round(r["lon"], 4)
        if r["genres"]:
            s["g"] = r["genres"]
        s["fmt"] = r["fmt"]
        br = re.sub(r"\D", "", str(r["br"]).split(",")[0])
        if br and 0 < int(br) < 1000:
            s["br"] = int(br)
        if r["meta"]:
            s["meta"] = 1
        if r["logo"].startswith("http"):
            s["logo"] = r["logo"]
        if r["web"].startswith("http"):
            s["web"] = r["web"]
        s["pop"] = r["votes"]
        if sid in ov.get("logos", {}):  # sigle alese de mână (Radio Browser n-are una bună)
            s["logo"] = ov["logos"][sid]
        stations.append(s)

    counties = [{"c": c, "n": n, "seat": seat} for c, n, seat, _ in geo.COUNTIES]
    doc = {"v": 1, "genres": [{"k": k, "n": n} for k, n, _ in GENRES], "counties": counties, "stations": stations}

    with open(os.path.join(ROOT, "data", "review.txt"), "w") as f:
        for s in stations:
            f.write(f"{s['t']} {s.get('c','--'):3} {s['n'][:34]:34} {(s.get('city') or '')[:18]:18} {s.get('f',''):7} {','.join(s.get('g',[]))[:26]:26} {s['fmt']}{'*' if s.get('meta') else ' '} {s['u'][:60]}\n")
    from collections import Counter
    print("posturi:", len(stations), Counter(s["t"] for s in stations))
    print("fără județ (online):", sum(1 for s in stations if s["t"] == "o" and "c" not in s))
    return doc, stations


if __name__ == "__main__":
    main()
