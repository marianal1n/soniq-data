#!/usr/bin/env python3
"""România pentru SONIQ: posturile cu flux online (Radio Browser, verificate și curățate de curate.py)
puse pe județe după licențele CNA — în fiecare județ, ce posturi se aud pe FM, pe ce frecvență și în ce localitate.

    python3 tools/romania.py        # scrie dist/v1/ro.json și data/review-ro.txt

Posturile din lista CNA fără flux online găsit rămân în județ ca „doar pe FM” (fără adresă, nu se pot reda)."""
import json, os, re, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import curate, geo, stable

ROOT = os.path.join(os.path.dirname(__file__), "..")
norm = geo.norm
geo.ALIAS.update({"dr tr severin": "drobeta turnu severin", "drobeta tr severin": "drobeta turnu severin",
                  "tg mures": "targu mures", "tg jiu": "targu jiu", "rm valcea": "ramnicu valcea", "rm sarat": "ramnicu sarat"})

THEMES = [("relig", ["crestin"]), ("rock", ["rock"]), ("dance", ["dance"]), ("manele", ["manele"]), ("popular", ["populara"]),
          ("folclor", ["populara"]), ("inform", ["stiri"]), ("stiri", ["stiri"]), ("sport", ["stiri"]), ("cultural", ["stiri"]),
          ("muzical", ["pop"]), ("general", ["pop"]), ("copii", ["copii"]), ("jazz", ["jazz"])]


def key(n):
    """Numele fără „radio”, spații, diacritice: „RADIO ZU” = „Radio ZU” = „ZU Radio”."""
    k = norm(n)
    k = re.sub(r"\b(radio|statia|post)\b", " ", k)
    return re.sub(r"\s+", "", k)


def title(n):
    """„RADIO VOCEA SPERANȚEI” → „Radio Vocea Speranței”, cu sigle păstrate."""
    out = []
    for w in n.split():
        lw = w.lower()
        if lw in ("fm", "am", "rfm", "rve", "sos", "s.o.s.", "dj", "tv", "mdi", "hd") or re.fullmatch(r"[\d'.,]+", w):
            out.append(w.upper())
        else:
            out.append(lw[:1].upper() + lw[1:])
    return " ".join(out).replace("Ș", "Ș").strip(" -")


def build():
    doc, stations = curate.build()
    prev = os.path.join(ROOT, "dist", "v1", "ro.json")  # lista publicată data trecută
    stations = stable.stabilize(stations, json.load(open(prev))["stations"] if os.path.exists(prev) else [])
    byid = {s["id"]: s for s in stations}
    cna = json.load(open(os.path.join(ROOT, "data", "cache", "cna.json")))
    brands = json.load(open(os.path.join(ROOT, "data", "brands.json")))
    brands = sorted(((k, v) for k, v in brands.items() if not k.startswith("_")), key=lambda kv: -len(kv[0]))
    bykey = defaultdict(list)
    for s in stations:
        bykey[key(s["n"])].append(s)

    def best(cands, code, city):
        """Același oraș > același județ > național > (doar dacă numele e identic) alt județ."""
        def score(s):
            return (s.get("city") == city and s.get("c") == code, s.get("c") == code, s["t"] == "n", s["t"] == "l", s.get("pop", 0))
        return max(cands, key=score) if cands else None

    warn = set()

    def match(brand, code, city):
        k = norm(brand)
        for prefix, target in brands:
            if k.startswith(prefix):
                if target.startswith("*"):
                    pre = target[1:]
                    return best([s for s in stations if norm(s["n"]).startswith(pre)], code, city)
                if target in byid:
                    return byid[target]
                warn.add(f"brands.json: „{prefix}” → {target} nu mai există în listă")
                break
        kk = key(brand)
        if not kk:
            return None
        exact = bykey.get(kk, [])
        here = [s for s in exact if s.get("c") == code or s["t"] == "n"]
        if here:  # același nume în județul licenței (sau rețea națională): sigur el
            return best(here, code, city)
        if len(kk) >= 4:
            # „ROCK FM MUZICAL” → Rock FM, „RADIO STAR” (Sebeș) → Star FM Sebeș: prefix, doar în același județ
            near = [s for k2, l in bykey.items() if len(k2) >= 4 and (kk.startswith(k2) or k2.startswith(kk)) for s in l
                    if s.get("c") == code or s["t"] == "n"]
            if near:
                return best(near, code, city)
        # aceeași rețea, cu fluxul din alt județ (nume identic, cel puțin 3 litere)
        return best(exact, code, city) if len(kk) >= 3 else None

    def place(loc, jud):
        code = geo.county_by_name(jud)
        seat = next((c for c in geo.COUNTIES if c[0] == code), None)
        parts = [p.strip() for p in re.split(r"\s+-\s+", loc) if p.strip()]
        found = []
        for p in parts:
            if seat and norm(p) == norm(seat[1]):  # amplasamentul „CLUJ - FELEAC”: județul → reședința
                p = seat[2]
            g = geo.geocode(p, code)
            if g and g[3] == code:
                found.append(g)
        if not found and seat:
            found = [geo.geocode(seat[2], code)]
        if not found or not found[0]:
            return None
        g = max(found, key=lambda g: g[4])  # „CERBU - NOVACI” → Novaci, orașul
        return code, g[0], g[1], g[2]

    fm = defaultdict(list)  # județ → [id, frecvență, localitate]
    fm_only = {}
    unmatched = Counter()

    def add(loc, jud, brand, freq, theme=""):
        pl = place(loc, jud)
        if not pl:
            unmatched["(fără localitate) " + loc] += 1
            return
        code, cname, lat, lon = pl
        s = match(brand, code, cname)
        if s is None:
            fid = "fm-" + curate.slug(brand) + "-" + code.lower()
            s = fm_only.get(fid)
            if s is None:
                g = sorted({x for k, gs in THEMES if k in norm(theme) for x in gs})
                s = {"id": fid, "n": title(brand), "t": "l", "u": None, "c": code, "city": cname, "lat": round(lat, 4),
                     "lon": round(lon, 4), "g": g[:2], "pop": 0}
                fm_only[fid] = s
            unmatched[brand] += 1
        if not any(x[0] == s["id"] and x[1] == freq for x in fm[code]):
            fm[code].append([s["id"], freq, cname])

    for r in cna["licente"]:
        add(r["loc"], r["jud"], r["name"], r["f"], r.get("theme", ""))
    for r in cna["srr"]:
        add(r["site"], r["jud"], r["name"], r["f"], "informativ")

    def fsort(x):
        try:
            return float(x[1].split()[0]) + (10000 if "AM" in x[1] else 0)
        except ValueError:
            return 99999
    for c in doc["counties"]:
        c["fm"] = sorted(fm.get(c["c"], []), key=fsort)
    doc["stations"] = stations + sorted(fm_only.values(), key=lambda s: s["id"])
    doc["v"] = 2
    doc["country"] = "RO"
    doc["sources"] = {"stations": "Radio Browser (radio-browser.info, domeniu public)",
                      "fm": "CNA – licențe audiovizuale radio (cna.ro)", "places": "GeoNames (CC BY 4.0)"}

    with open(os.path.join(ROOT, "data", "review-ro.txt"), "w") as f:
        for c in doc["counties"]:
            f.write(f"\n== {c['n']} ({c['c']}) — {len({x[0] for x in c['fm']})} posturi pe FM\n")
            for sid, fr, loc in c["fm"]:
                s = byid.get(sid) or fm_only[sid]
                f.write(f"   {fr:>8}  {s['n'][:36]:36} {loc[:22]:22} {'' if s.get('u') else '(doar pe FM)'}\n")
        f.write("\n== Nume CNA fără flux online găsit\n")
        for n, k in unmatched.most_common():
            f.write(f"   {k:3}  {n}\n")
    for w in sorted(warn):
        print("ATENȚIE", w)
    playable = sum(1 for l in fm.values() for x in l if x[0] in byid)
    total = sum(len(l) for l in fm.values())
    print(f"România: {len(fm)} județe, {total} frecvențe ({playable} cu flux online), "
          f"{len(fm_only)} posturi doar pe FM, {len(stations)} posturi cu flux")
    return doc


if __name__ == "__main__":
    doc = build()
    os.makedirs(os.path.join(ROOT, "dist", "v1"), exist_ok=True)
    json.dump(doc, open(os.path.join(ROOT, "dist", "v1", "ro.json"), "w"), ensure_ascii=False, separators=(",", ":"))
