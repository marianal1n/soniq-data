#!/usr/bin/env python3
"""Verifică fluxurile din data/raw/rb-ro.json: răspunde? ce format? trimite titluri ICY?
Scrie data/raw/check.json (cheia = stationuuid)."""
import json, socket, ssl, sys, time, re
from urllib.parse import urlsplit, urljoin
from concurrent.futures import ThreadPoolExecutor

UA = "SONIQ/1.0 (Android radio; verificare fluxuri)"
# pe Mac, Python-ul de la python.org n-are certificatele sistemului; pe Linux (GitHub Actions) le are
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem") if sys.platform == "darwin" else ssl.create_default_context()

def get(url, hops=0):
    u = urlsplit(url)
    host, port = u.hostname, u.port or (443 if u.scheme == "https" else 80)
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    s = socket.create_connection((host, port), timeout=8)
    if u.scheme == "https":
        s = CTX.wrap_socket(s, server_hostname=host)
    s.settimeout(8)
    req = f"GET {path} HTTP/1.0\r\nHost: {u.netloc}\r\nUser-Agent: {UA}\r\nIcy-MetaData: 1\r\nAccept: */*\r\nConnection: close\r\n\r\n"
    s.sendall(req.encode())
    t0 = time.time()
    buf = b""
    while b"\r\n\r\n" not in buf and len(buf) < 32768:
        d = s.recv(4096)
        if not d: break
        buf += d
    head, _, body = buf.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    m = re.match(r"(HTTP/\d\.\d|ICY)\s+(\d+)", lines[0])
    code = int(m.group(2)) if m else 0
    hdr = {}
    for l in lines[1:]:
        if ":" in l:
            k, v = l.split(":", 1); hdr[k.strip().lower()] = v.strip()
    if code in (301, 302, 303, 307, 308) and "location" in hdr and hops < 5:
        s.close()
        return get(urljoin(url, hdr["location"]), hops + 1)
    while len(body) < 24000 and time.time() - t0 < 8:
        try:
            d = s.recv(8192)
        except socket.timeout:
            break
        if not d: break
        body += d
    s.close()
    return url, code, hdr, body

def sniff(b):
    if b[:7] == b"#EXTM3U": return "hls" if b"#EXT-X" in b[:2000] else "m3u"
    if b[:4] == b"OggS": return "ogg"
    if b[:3] == b"ID3": return "mp3"
    if b[:5].lower() in (b"<!doc", b"<html") or b"<html" in b[:300].lower(): return "html"
    if b[:10].lower().startswith(b"[playlist]"): return "pls"
    mp3 = aac = 0
    for i in range(min(len(b) - 2, 20000)):
        if b[i] == 0xFF:
            n = b[i + 1]
            if (n & 0xF6) == 0xF0: aac += 1
            elif (n & 0xE0) == 0xE0 and (n & 0x06) != 0: mp3 += 1
    if aac > 5 and aac >= mp3 / 3: return "aac"
    if mp3 > 5: return "mp3"
    if b[:4] == b"FLV\x01": return "flv"
    return "?"

def probe(url, depth=0):
    """Răspunde fluxul? Listele .m3u/.pls se deschid și se verifică prima adresă din ele."""
    r = {"url": url}
    try:
        final, code, hdr, body = get(url)
        fmt = sniff(body)
        if code == 200 and fmt in ("m3u", "pls") and depth == 0:
            inner = re.findall(rb"https?://[^\s\"'<>]+", body)
            if inner:
                sub = probe(inner[0].decode("latin-1"), 1)
                sub["url"] = url
                return sub
        r.update(final=final, code=code, ct=hdr.get("content-type", ""), metaint=int(hdr.get("icy-metaint", "0") or 0),
                 icyname=hdr.get("icy-name", ""), br=hdr.get("icy-br", ""), fmt=fmt, bytes=len(body))
    except Exception as e:
        r["err"] = type(e).__name__ + ": " + str(e)[:80]
    return r


def ok(r):
    return r.get("code") == 200 and r.get("fmt") in ("mp3", "aac", "ogg", "hls")


def check(st):
    return st["stationuuid"], probe(st["url_resolved"] or st["url"])

if __name__ == "__main__":
    d = json.load(open(sys.argv[1]))
    out = {}
    with ThreadPoolExecutor(40) as ex:
        for i, (k, r) in enumerate(ex.map(check, d)):
            out[k] = r
            if i % 100 == 0: print(i, file=sys.stderr, flush=True)
    json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=0)
    print("ok", sum(1 for r in out.values() if ok(r)), "din", len(out))
