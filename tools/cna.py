#!/usr/bin/env python3
"""Licențele radio din România, după listele publice ale CNA (Consiliul Național al Audiovizualului):
cine emite pe ce frecvență, în ce localitate. Scrie data/cache/cna.json.

    python3 tools/cna.py            # descarcă PDF-urile actuale de pe cna.ro și le citește

Sursa: https://cna.ro → „Situații privind licențele audiovizuale” (Radio - Licențe audiovizuale,
Frecvențele serviciilor de programe Radio ale SRR). PDF-urile folosesc un font vechi pentru diacritice."""
import json, os, re, ssl, sys, urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
CACHE = os.path.join(ROOT, "data", "cache")
PAGE = ("https://cna.ro/a-situatii-privind-licentele-audiovizuale-avizele-de-furnizare-a-serviciilor-media-audiovizuale-"
        "la-cerere-avizele-de-retransmisie-si-autorizatiile-de-re-fl7wut28fqxu5c0y94sohaf7/")
UA = {"User-Agent": "SONIQ-data/1.0 (+https://github.com/marianal1n/soniq-data)"}
FIX = str.maketrans({"}": "Ț", "]": "ț", "\\": "ă", "|": "Ă", "{": "Ș", "[": "ș", "~": "Î"})


# pe Mac, Python-ul de la python.org n-are certificatele sistemului; pe GitHub Actions (Linux) nu e nevoie
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem") if sys.platform == "darwin" else ssl.create_default_context()


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60, context=CTX).read()


def pdf_links():
    html = get(PAGE).decode("utf-8", "replace")
    links = set(re.findall(r'https://media\.cna\.ro/[^"<> ]+\.pdf', html))
    lic = next((l for l in links if "Radio_Licente_audiovizuale" in l), None)
    srr = next((l for l in links if "Frecventele_serviciilor_de_programe_Radio_ale_SRR" in l), None)
    if not lic or not srr:
        raise SystemExit("Nu găsesc PDF-urile radio pe pagina CNA — s-a schimbat pagina?")
    return lic, srr


def rows(pdf, header_first):
    """Rânduri ca dict coloană → text, după pozițiile titlurilor de coloană; rândurile rupte se lipesc de cel de sus."""
    import pdfplumber  # pip install pdfplumber (doar pentru pasul ăsta)
    out = []
    with pdfplumber.open(pdf) as p:
        for pg in p.pages:
            ws = [dict(w, text=w["text"].translate(FIX)) for w in pg.extract_words()]
            head = [w for w in ws if w["text"] == header_first]
            if not head:
                continue
            htop = head[0]["top"]
            cols = sorted([w for w in ws if abs(w["top"] - htop) < 3], key=lambda w: w["x0"])
            # „NUME PROGRAM”, „DATA LIC.” sunt câte o singură coloană
            bounds = [(c["x0"] - 4, c["text"]) for c in cols if c["text"] not in ("PROGRAM", "LIC.")]
            lines = {}
            for w in ws:
                if w["top"] <= htop + 3:
                    continue
                key = round(w["top"] / 3)
                lines.setdefault(key, []).append(w)
            for key in sorted(lines):
                r = {}
                for w in sorted(lines[key], key=lambda w: w["x0"]):
                    name = bounds[0][1]
                    for x, n in bounds:
                        if w["x0"] >= x:
                            name = n
                    r[name] = (r.get(name, "") + " " + w["text"]).strip()
                if r.get(header_first):
                    out.append(r)
                elif out:  # continuarea rândului de sus (nume pe două rânduri)
                    for k, v in r.items():
                        out[-1][k] = (out[-1].get(k, "") + " " + v).strip()
    return out


def main():
    os.makedirs(CACHE, exist_ok=True)
    lic_url, srr_url = pdf_links()
    lic_pdf, srr_pdf = os.path.join(CACHE, "cna-licente.pdf"), os.path.join(CACHE, "cna-srr.pdf")
    for u, f in ((lic_url, lic_pdf), (srr_url, srr_pdf)):
        open(f, "wb").write(get(u))
    lic = []
    for r in rows(lic_pdf, "LOCALITATE"):
        m = re.search(r"\b(\d{2,4}\.\d{1,3})\b", r.get("FRECV.", ""))
        if not m:
            continue
        v = float(m.group(1))
        lic.append({"loc": r["LOCALITATE"], "jud": r.get("JUDET", ""), "f": f"{v:.1f}" if v < 200 else f"{int(v)} AM", "name": r.get("NUME", ""),
                    "theme": r.get("TEMATICA", ""), "owner": r.get("SOCIETATE", ""), "cov": r.get("ACOPERIRE", "")})
    srr = []
    for r in rows(srr_pdf, "NUME"):
        m = re.search(r"\b(\d{2,4}\.\d{1,3})\b", r.get("FRECVENȚA", "") or r.get("FRECVENTA", ""))
        if not m:
            continue
        v = float(m.group(1))
        f = f"{v:.1f}" if v < 200 else f"{int(v)} AM"  # undele medii sunt în kHz
        srr.append({"name": r["NUME"], "site": r.get("AMPLASAMENT", ""), "jud": r.get("JUDEȚ", r.get("JUDET", "")), "f": f})
    json.dump({"source": [lic_url, srr_url], "licente": lic, "srr": srr}, open(os.path.join(CACHE, "cna.json"), "w"),
              ensure_ascii=False, indent=0)
    print(f"CNA: {len(lic)} licențe private, {len(srr)} frecvențe SRR")


if __name__ == "__main__":
    main()
