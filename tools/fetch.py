#!/usr/bin/env python3
"""Descarcă lista de posturi din Radio Browser (radio-browser.info, date în domeniul public).

    python3 tools/fetch.py      # scrie data/raw/rb-all.json (toată lumea, doar fluxuri care merg)
                                #   și data/raw/rb-ro.json (România, toate, le verifică tools/check.py)

Radio Browser are mai multe servere-oglindă; lista lor vine de la all.api.radio-browser.info.
Se încearcă pe rând până răspunde unul."""
import json, os, random, ssl, sys, urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "data", "raw")
UA = {"User-Agent": "SONIQ-data/1.0 (+https://github.com/marianal1n/soniq-data)"}
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem") if sys.platform == "darwin" else ssl.create_default_context()
FALLBACK = ["de1.api.radio-browser.info", "de2.api.radio-browser.info", "fi1.api.radio-browser.info"]


def get(url, timeout=300):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout, context=CTX).read()


def servers():
    try:
        names = sorted({s["name"] for s in json.loads(get("https://all.api.radio-browser.info/json/servers", 30))})
        random.shuffle(names)  # cererea lor: împărțim încărcarea între oglinzi
        return names + [n for n in FALLBACK if n not in names]
    except Exception as e:
        print("lista de servere nu vine:", e, file=sys.stderr)
        return FALLBACK


def fetch(path):
    last = None
    for host in servers():
        try:
            data = json.loads(get(f"https://{host}{path}"))
            if isinstance(data, list) and data:
                print(f"{host}{path}: {len(data)} posturi")
                return data
        except Exception as e:
            last = e
            print(f"{host}: {e}", file=sys.stderr)
    raise SystemExit(f"Radio Browser nu răspunde: {last}")


def save(name, data):
    tmp = os.path.join(RAW, name + ".tmp")
    json.dump(data, open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, os.path.join(RAW, name))


def main():
    os.makedirs(RAW, exist_ok=True)
    world = fetch("/json/stations?hidebroken=true&limit=200000")
    if len(world) < 20000:  # un răspuns trunchiat ar goli jumătate din țări
        raise SystemExit(f"prea puține posturi ({len(world)}) — nu suprascriu lista")
    save("rb-all.json", world)
    ro = fetch("/json/stations/bycountrycodeexact/RO?limit=10000")
    if len(ro) < 500:
        raise SystemExit(f"prea puține posturi românești ({len(ro)})")
    save("rb-ro.json", ro)


if __name__ == "__main__":
    main()
