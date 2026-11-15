"""Județe (cod, nume, reședință), contururi simplificate și geocodare de localități din GeoNames."""
import json, os, re, unicodedata

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "data", "raw")

# cod auto, nume, reședință, cheia din geoBoundaries
COUNTIES = [
    ("AB", "Alba", "Alba Iulia", "ALBA"), ("AR", "Arad", "Arad", "ARAD"), ("AG", "Argeș", "Pitești", "ARGES"),
    ("BC", "Bacău", "Bacău", "BACAU"), ("BH", "Bihor", "Oradea", "BIHOR"), ("BN", "Bistrița-Năsăud", "Bistrița", "BISTRITA-NASAUD"),
    ("BT", "Botoșani", "Botoșani", "BOTOSANI"), ("BV", "Brașov", "Brașov", "BRASOV"), ("BR", "Brăila", "Brăila", "BRAILA"),
    ("B", "București", "București", "BUCURESTI"), ("BZ", "Buzău", "Buzău", "BUZAU"), ("CS", "Caraș-Severin", "Reșița", "CARAS-SEVERIN"),
    ("CL", "Călărași", "Călărași", "CALARASI"), ("CJ", "Cluj", "Cluj-Napoca", "CLUJ"), ("CT", "Constanța", "Constanța", "CONSTANTA"),
    ("CV", "Covasna", "Sfântu Gheorghe", "COVASNA"), ("DB", "Dâmbovița", "Târgoviște", "DAMBOVITA"), ("DJ", "Dolj", "Craiova", "DOLJ"),
    ("GL", "Galați", "Galați", "GALATI"), ("GR", "Giurgiu", "Giurgiu", "GIURGIU"), ("GJ", "Gorj", "Târgu Jiu", "GORJ"),
    ("HR", "Harghita", "Miercurea Ciuc", "HARGHITA"), ("HD", "Hunedoara", "Deva", "HUNEDOARA"), ("IL", "Ialomița", "Slobozia", "IALOMITA"),
    ("IS", "Iași", "Iași", "IASI"), ("IF", "Ilfov", "Buftea", "ILFOV"), ("MM", "Maramureș", "Baia Mare", "MARAMURES"),
    ("MH", "Mehedinți", "Drobeta-Turnu Severin", "MEHEDINTI"), ("MS", "Mureș", "Târgu Mureș", "MURES"), ("NT", "Neamț", "Piatra Neamț", "NEAMT"),
    ("OT", "Olt", "Slatina", "OLT"), ("PH", "Prahova", "Ploiești", "PRAHOVA"), ("SM", "Satu Mare", "Satu Mare", "SATU MARE"),
    ("SJ", "Sălaj", "Zalău", "SALAJ"), ("SB", "Sibiu", "Sibiu", "SIBIU"), ("SV", "Suceava", "Suceava", "SUCEAVA"),
    ("TR", "Teleorman", "Alexandria", "TELEORMAN"), ("TM", "Timiș", "Timișoara", "TIMIS"), ("TL", "Tulcea", "Tulcea", "TULCEA"),
    ("VS", "Vaslui", "Vaslui", "VASLUI"), ("VL", "Vâlcea", "Râmnicu Vâlcea", "VALCEA"), ("VN", "Vrancea", "Focșani", "VRANCEA"),
]
BY_GB = {c[3]: c[0] for c in COUNTIES}
NAME = {c[0]: c[1] for c in COUNTIES}


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower().replace("ş", "ș").replace("ţ", "ț"))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def county_by_name(s):
    n = norm(s)
    for code, name, seat, gb in COUNTIES:
        if n in (norm(name), norm(gb)):
            return code
    return None


# ---------- contururi ----------
def _dp(pts, eps):
    """Douglas–Peucker."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    L = (dx * dx + dy * dy) ** 0.5
    imax, dmax = 0, 0
    for i in range(1, len(pts) - 1):
        x, y = pts[i]
        # inel închis (capetele coincid): distanța până la punct, nu până la dreaptă
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / L if L > 1e-12 else ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        if d > dmax:
            imax, dmax = i, d
    if dmax > eps:
        a = _dp(pts[: imax + 1], eps)
        return a[:-1] + _dp(pts[imax:], eps)
    return [pts[0], pts[-1]]


def load_polys():
    d = json.load(open(os.path.join(RAW, "ro-adm1.geojson")))
    out = {}
    for f in d["features"]:
        code = BY_GB[f["properties"]["shapeName"]]
        g = f["geometry"]
        out[code] = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return out


def simplified_geojson(eps=0.004):
    feats = []
    for code, polys in load_polys().items():
        mp = []
        for poly in polys:
            rings = []
            for ring in poly:
                r = _dp(ring, eps)
                if len(r) >= 4:
                    rings.append([[round(x, 3), round(y, 3)] for x, y in r])
            if rings:
                mp.append(rings)
        feats.append({"type": "Feature", "properties": {"c": code}, "geometry": {"type": "MultiPolygon", "coordinates": mp}})
    return {"type": "FeatureCollection", "features": feats}


def _inside(x, y, ring):
    c = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi:
            c = not c
        j = i
    return c


_POLYS = None


def county_at(lat, lon):
    global _POLYS
    if _POLYS is None:
        _POLYS = load_polys()
    for code, polys in _POLYS.items():
        for poly in polys:
            if _inside(lon, lat, poly[0]) and not any(_inside(lon, lat, h) for h in poly[1:]):
                return code
    return None


# ---------- localități ----------
_PLACES = None
ALIAS = {
    "bucharest": "bucuresti", "bucarest": "bucuresti", "buch": "bucuresti", "bucuresti ilfov": "bucuresti",
    "cluj napoca": "cluj napoca", "cluj": "cluj napoca", "rm sarat": "ramnicu sarat", "rm valcea": "ramnicu valcea",
    "timisoara": "timisoara", "nagyvarad": "oradea", "margitta": "marghita", "szekelyudvarhely": "odorheiu secuiesc",
    "kezdivasarhely": "targu secuiesc", "sepsiszentgyorgy": "sfantu gheorghe", "csikszereda": "miercurea ciuc",
    "kolozsvar": "cluj napoca", "marosvasarhely": "targu mures", "gyergyo": "gheorgheni", "gyergyoszentmiklos": "gheorgheni",
    "szekelykeresztur": "cristuru secuiesc", "sighet": "sighetu marmatiei", "campulung muscel": "campulung",
    "drobeta": "drobeta turnu severin", "turnu severin": "drobeta turnu severin", "bistritai": "bistrita",
}


def pretty(name, alts):
    """Numele cu diacritice (GeoNames are uneori „Onesti”): caut în numele alternative varianta cu cele mai multe."""
    n = norm(name)
    best = name
    for a in [name] + alts.split(","):
        if norm(a) == n and sum(ch in "ăâîșțşţ" for ch in a.lower()) > sum(ch in "ăâîșțşţ" for ch in best.lower()):
            best = a
    best = best.replace("ş", "ș").replace("ţ", "ț").replace("Ş", "Ș").replace("Ţ", "Ț")
    if best.startswith("Sector "):
        return "București"
    return {"Bucharest": "București", "Miercurea-Ciuc": "Miercurea Ciuc"}.get(best, best)


def places():
    """nume normalizat → listă de (nume, lat, lon, cod județ, populație), cea mai mare prima."""
    global _PLACES
    if _PLACES is not None:
        return _PLACES
    adm = {}
    for line in open(os.path.join(RAW, "admin1.txt"), encoding="utf-8"):
        k, name, ascii_, _ = line.rstrip("\n").split("\t")
        if k.startswith("RO."):
            adm[k[3:]] = county_by_name(ascii_.replace(" County", ""))
    P = {}
    for line in open(os.path.join(RAW, "RO.txt"), encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if f[6] != "P":
            continue
        pop = int(f[14] or 0)
        code = adm.get(f[10])
        rec = (pretty(f[1], f[3]), float(f[4]), float(f[5]), code, pop)
        # GeoNames n-are populația pentru multe orașe: contează și rangul (reședință, oraș/comună)
        rank = 3 if f[7] in ("PPLC", "PPLA") else 2.5 if pop >= 10000 else 2 if f[7] == "PPLA2" else 1 if pop else 0
        main = {norm(f[1]), norm(f[2])}
        alt = {norm(a) for a in f[3].split(",") if a} - main if pop >= 5000 else set()  # nume maghiare/germane, doar orașe
        for n in main:
            if n:
                P.setdefault(n, []).append((1, rank, rec))
        for n in alt:
            if n:
                P.setdefault(n, []).append((0, rank, rec))
    for n, l in P.items():
        l.sort(key=lambda t: (-t[0], -t[1], -t[2][4]))
        P[n] = [t[2] for t in l]
    _PLACES = P
    return P


def geocode(city, county=None, near=None):
    """(nume, lat, lon, județ, populație) sau None; cu `county` alege localitatea din județul acela,
    cu `near` (lat, lon) pe cea mai apropiată de punct (dacă e la cel mult 40 km)."""
    n = norm(city)
    n = ALIAS.get(n, n)
    if n == "bucuresti":
        return ("București", 44.4325, 26.1039, "B", 1877155)
    l = places().get(n)
    if not l:
        return None
    if near:
        best = min(l, key=lambda r: dist(near, (r[1], r[2])))
        return best if dist(near, (best[1], best[2])) < 40 else None
    if county:
        for r in l:
            if r[3] == county:
                return r
    return l[0]


def dist(a, b):
    """km, aproximativ (suficient la scara României)."""
    import math
    dy = (a[0] - b[0]) * 111.2
    dx = (a[1] - b[1]) * 111.2 * math.cos(math.radians((a[0] + b[0]) / 2))
    return (dx * dx + dy * dy) ** 0.5


_TOWNS = None


def is_town(p):
    """Localitatea e oraș sau comună (are rang în GeoNames), nu un sat oarecare?"""
    nearest(p[1], p[2])  # încarcă lista
    return any(abs(t[1] - p[1]) < 1e-4 and abs(t[2] - p[2]) < 1e-4 for t in _TOWNS)


def nearest(lat, lon):
    """Cel mai apropiat oraș/comună (rang ≥ 2) de un punct."""
    global _TOWNS
    if _TOWNS is None:
        seen = {}
        for line in open(os.path.join(RAW, "RO.txt"), encoding="utf-8"):
            f = line.rstrip("\n").split("\t")
            pop = int(f[14] or 0)
            if f[6] == "P" and (f[7] in ("PPLC", "PPLA", "PPLA2") or pop >= 10000):
                rank = 3 if f[7] in ("PPLC", "PPLA") else 2.5 if pop >= 10000 else 2
                seen[f[0]] = (pretty(f[1], f[3]), float(f[4]), float(f[5]), None, pop, rank)
        _TOWNS = list(seen.values())
    near = [r for r in _TOWNS if r[5] >= 2.5 and dist((lat, lon), (r[1], r[2])) < 12]
    if near:  # orașul din apropiere (reședința înaintea satelor de lângă), cel mai aproape
        best = min(near, key=lambda r: dist((lat, lon), (r[1], r[2])) - 6 * (r[5] == 3))
    else:
        best = min(_TOWNS, key=lambda r: dist((lat, lon), (r[1], r[2])))
        if dist((lat, lon), (best[1], best[2])) > 8:
            return None
    return best[:3] + (county_at(best[1], best[2]), best[4])
