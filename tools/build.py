#!/usr/bin/env python3
"""Reface toată lista SONIQ: o rulează GitHub Actions în fiecare săptămână (.github/workflows/update.yml).

    python3 tools/build.py              # descarcă tot din nou
    python3 tools/build.py --offline    # doar refă fișierele din ce e deja descărcat

Scrie dist/v1/: index.json (ce fișiere există și amprenta lor), ro.json (România pe județe, cu frecvențele FM),
top.json (cele mai ascultate din lume) și c/<țară>.json. Aplicația citește întâi index.json și descarcă
doar fișierele a căror amprentă s-a schimbat."""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(__file__))
import check, cna, fetch, romania, world

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIST = os.path.join(ROOT, "dist", "v1")
BASE = "https://raw.githubusercontent.com/marianal1n/soniq-data/main/dist/v1/"


def step(name):
    print(f"\n== {name}", flush=True)


def main():
    offline = "--offline" in sys.argv
    if not offline:
        step("Radio Browser")
        fetch.main()
        step("verific fluxurile din România")
        ro = json.load(open(os.path.join(ROOT, "data", "raw", "rb-ro.json")))
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(40) as ex:
            out = dict(ex.map(check.check, ro))
        json.dump(out, open(os.path.join(ROOT, "data", "raw", "check.json"), "w"), ensure_ascii=False)
        print("merg", sum(1 for r in out.values() if check.ok(r)), "din", len(out))
        step("licențele CNA")
        try:
            cna.main()
        except BaseException as e:  # pagina CNA s-a schimbat sau nu răspunde: rămân licențele de data trecută
            print("ATENȚIE: CNA nu merge acum, folosesc lista salvată:", e)

    step("România")
    prev = os.path.join(DIST, "ro.json")
    before = sum(1 for s in json.load(open(prev))["stations"] if s.get("u")) if os.path.exists(prev) else 0
    doc = romania.build()
    now = sum(1 for s in doc["stations"] if s.get("u"))
    if now < 400 or now < before * 0.8:
        raise SystemExit(f"România: doar {now} posturi cu flux (înainte {before}) — ceva e greșit, nu public")
    ro_h, ro_b = world.dump(prev, doc)

    step("lume")
    countries, top = world.main()

    index = {"v": 2, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "base": BASE,
             "ro": {"f": "ro.json", "h": ro_h, "b": ro_b, "k": now},
             "top": dict(top, f="top.json"),
             "genres": world.genre_list(),
             "countries": [dict(c, f="c/" + c["cc"].lower() + ".json") for c in countries],
             "sources": {"stations": "Radio Browser — radio-browser.info (public domain)",
                         "fm": "CNA — licențe audiovizuale radio (cna.ro)",
                         "places": "GeoNames (CC BY 4.0), geoBoundaries (CC BY 4.0)"}}
    # „updated” se schimbă la fiecare rulare; ca să nu facă un commit pe săptămână degeaba, îl păstrez dacă restul e la fel
    ip = os.path.join(DIST, "index.json")
    if os.path.exists(ip):
        old = json.load(open(ip))
        if {k: v for k, v in old.items() if k != "updated"} == {k: v for k, v in index.items() if k != "updated"}:
            index["updated"] = old["updated"]
    world.dump(ip, index)
    print(f"\ngata: România {now} posturi, lume {sum(c['k'] for c in countries)} în {len(countries)} țări")


if __name__ == "__main__":
    main()
