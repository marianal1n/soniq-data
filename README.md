# SONIQ — lista de posturi

Lista de posturi de radio a aplicației [SONIQ](https://autofreon.ro/soniq), actualizată automat în fiecare săptămână
de GitHub Actions, independent de aplicație. Aplicația citește `dist/v1/index.json` și descarcă doar fișierele schimbate.

| Fișier | Ce e |
|---|---|
| `dist/v1/index.json` | țările, genurile, amprenta (`h`) și mărimea (`b`) fiecărui fișier |
| `dist/v1/ro.json` | România: posturi naționale, locale și online, pe județe; în fiecare județ, ce posturi se aud pe FM, pe ce frecvență și unde |
| `dist/v1/top.json` | cele mai ascultate posturi din lume (pentru „Surpriză”) |
| `dist/v1/c/<țară>.json` | posturile unei țări (cod ISO 3166-1, litere mici) |

## Cum se face

```
pip install pdfplumber
python3 tools/build.py            # tot: descarcă, verifică, construiește
python3 tools/build.py --offline  # doar reconstruiește din ce e descărcat
```

1. `tools/fetch.py` — toate posturile din [Radio Browser](https://www.radio-browser.info) (fluxurile care merg).
2. `tools/check.py` — verifică fiecare flux românesc: răspunde, ce format are, trimite titlul melodiei.
3. `tools/cna.py` — licențele radio publicate de [CNA](https://cna.ro): cine emite pe ce frecvență, în ce localitate.
4. `tools/romania.py` (+ `curate.py`, `geo.py`) — posturile românești curățate și puse pe județe, cu frecvențele CNA;
   `tools/stable.py` ține id-urile stabile (favoritele din aplicație) și păstrează posturile care dispar din
   Radio Browser cât timp fluxul lor încă merge.
5. `tools/world.py` — restul lumii, câte un fișier pe țară.

Corecturile de mână: `data/overrides.json` (nume, orașe, sigle), `data/brands.json` (numele din CNA → postul din listă).
Ce a ieșit, de citit de om: `data/review.txt`, `data/review-ro.txt`.

## Surse și licențe

- Posturi și fluxuri: [Radio Browser](https://www.radio-browser.info) — domeniu public.
- Frecvențe FM/AM: Consiliul Național al Audiovizualului — [situații privind licențele audiovizuale](https://cna.ro).
- Localități: [GeoNames](https://www.geonames.org) — CC BY 4.0. Granițele județelor: [geoBoundaries](https://www.geoboundaries.org) — CC BY 4.0.
