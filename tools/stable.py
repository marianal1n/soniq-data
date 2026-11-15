#!/usr/bin/env python3
"""Lista nu are voie să „sară”: Radio Browser e editat de oricine, iar posturi mari dispar sau revin
sub alt nume (Radio ZU → „ZU Radio”, Pro FM → „ProFM”). Ce face aici, față de lista publicată data trecută:

  1. un post nou care e de fapt unul vechi (același nume sau același flux) primește id-ul vechi —
     favoritele din aplicație țin de id;
  2. un post vechi care lipsește acum din Radio Browser rămâne în listă cât timp fluxul lui încă merge;
     dacă nu mai merge nici fluxul, iese."""
import os, re, sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(__file__))
import check, geo

IDENTITY = ("id", "n", "t", "c", "city", "lat", "lon", "g", "f")
STREAM = ("u", "u2", "fmt", "br", "meta")


def key(n):
    k = re.sub(r"\b(radio|statia|post|fm)\b", " ", geo.norm(n))
    return re.sub(r"\s+", "", k)


def where(u):
    try:
        p = urlsplit(u)
        return (p.hostname or "") + p.path.rstrip("/;")
    except ValueError:
        return u


def stabilize(stations, prev, log=print):
    if not prev:
        return stations
    have = {s["id"] for s in stations}
    lost = {p["id"]: p for p in prev if p.get("u") and p["id"] not in have}
    by_key, by_url = {}, {}
    for p in lost.values():
        by_key.setdefault(key(p["n"]), []).append(p)
        for u in [p["u"]] + p.get("u2", []):
            by_url.setdefault(where(u), p)

    known = {x["id"] for x in prev}
    out, renamed = [], 0
    for s in stations:
        p = None
        if s["id"] not in known:
            p = next((x for u in [s["u"]] + s.get("u2", []) for x in [by_url.get(where(u))] if x and x["id"] in lost), None)
            if not p:
                p = next((x for x in by_key.get(key(s["n"]), []) if x["id"] in lost and
                          (x["t"] == "n" or s["t"] == "n" or x.get("c") == s.get("c"))), None)
        if p:
            # postul vechi, cu fluxul nou: id, nume, tip, loc și genuri rămân cum le știe aplicația
            m = {k: v for k, v in s.items() if k not in IDENTITY}
            m.update({k: p[k] for k in IDENTITY if k in p})
            if not m.get("logo") and p.get("logo"):
                m["logo"] = p["logo"]
            del lost[p["id"]]
            renamed += 1
            out.append(m)
        else:
            out.append(s)

    # ce a rămas: încă merge fluxul?
    def alive(p):
        for u in [p["u"]] + p.get("u2", []):
            if check.ok(check.probe(u)):
                return p, u
        return p, None

    kept = 0
    with ThreadPoolExecutor(20) as ex:
        for p, u in ex.map(alive, list(lost.values())):
            if u:
                q = dict(p)
                if u != p["u"]:
                    q["u"], q["u2"] = u, [x for x in [p["u"]] + p.get("u2", []) if x != u][:2]
                out.append(q)
                kept += 1
    log(f"stabil: {renamed} regăsite sub alt nume, {kept} păstrate (lipsesc din Radio Browser, dar merg), "
        f"{len(lost) - kept} scoase (nu mai merg)")
    return out
