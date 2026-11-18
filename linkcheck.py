#!/usr/bin/env python3
"""linkcheck.py: find broken links, missing images and redirect chains on your own website.
Usage: python3 linkcheck.py https://example.com OUTDIR [--max-pages 25] [--delay 0.5]
GET/HEAD only, honest User-Agent, one request at a time, respects robots.txt.
Writes OUTDIR/faults.csv, OUTDIR/pages.csv and OUTDIR/report.html (print-to-PDF ready).
Python 3.9+, standard library only. MIT licence."""
import csv, html, ssl, socket, sys, time, argparse, datetime
import urllib.request, urllib.error
from urllib.parse import urljoin, urldefrag, urlparse
from html.parser import HTMLParser
import urllib.robotparser

UA = "WebbitLinkCheck/1.0 (+https://github.com/ClaudVanDamCode/robin-linkcheck)"

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.title = ""; self._t = False; self._a = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self._a = [a["href"], ""]; self.links.append(("link", self._a))
        elif tag == "img" and a.get("src"):
            self.links.append(("image", [a["src"], a.get("alt") or ""]))
        elif tag == "script" and a.get("src"):
            self.links.append(("script", [a["src"], ""]))
        elif tag == "link" and a.get("href") and "stylesheet" in (a.get("rel") or ""):
            self.links.append(("stylesheet", [a["href"], ""]))
        elif tag == "title":
            self._t = True
    def handle_endtag(self, tag):
        if tag == "a": self._a = None
        if tag == "title": self._t = False
    def handle_data(self, d):
        if self._t: self.title += d
        if self._a is not None and len(self._a[1]) < 80: self._a[1] += d.strip() + " "

def fetch(url, method="GET", timeout=15):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
    class NoRedir(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    opener = urllib.request.build_opener(NoRedir)
    try:
        r = opener.open(req, timeout=timeout)
        body = r.read(3_000_000) if method == "GET" else b""
        return r.status, r.headers, body, None
    except urllib.error.HTTPError as e:
        return e.code, e.headers, b"", None
    except Exception as e:
        return None, None, b"", type(e).__name__ + ": " + str(e)[:120]

def resolve(url, method="HEAD", hops=6):
    """Follow redirects; return (final_status, chain, error, headers, body)."""
    chain = []
    for _ in range(hops):
        st, hd, body, err = fetch(url, method)
        if st in (405, 403, 501) and method == "HEAD":
            st, hd, body, err = fetch(url, "GET")
        if st in (301, 302, 303, 307, 308) and hd and hd.get("Location"):
            chain.append((st, url)); url = urljoin(url, hd["Location"]); continue
        return st, chain, err, hd, body, url
    return None, chain, "too many redirects", None, b"", url

def norm(u):
    u = urldefrag(u)[0]; pu = urlparse(u)
    return u + "/" if pu.path == "" and not pu.query else u

def cert_days(host):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as s:
            with ctx.wrap_socket(s, server_hostname=host) as t:
                exp = ssl.cert_time_to_seconds(t.getpeercert()["notAfter"])
        return int((exp - time.time()) // 86400), None
    except Exception as e:
        return None, str(e)[:150]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("start"); ap.add_argument("out")
    ap.add_argument("--max-pages", type=int, default=25); ap.add_argument("--delay", type=float, default=0.5)
    a = ap.parse_args()
    import os; os.makedirs(a.out, exist_ok=True)
    start = a.start if "://" in a.start else "https://" + a.start
    host = urlparse(start).hostname
    rp = urllib.robotparser.RobotFileParser(urljoin(start, "/robots.txt"))
    try: rp.read()
    except Exception: rp = None
    allowed = lambda u: rp is None or rp.can_fetch(UA, u)
    same = lambda u: (urlparse(u).hostname or "").removeprefix("www.") == host.removeprefix("www.")
    queue, seen_pages, pages, refs = [norm(start)], set(), [], {}
    while queue and len(pages) < a.max_pages:
        u = norm(queue.pop(0))
        if u in seen_pages or not allowed(u): continue
        seen_pages.add(u)
        st, chain, err, hd, body, final = resolve(u, "GET"); time.sleep(a.delay)
        ctype = (hd.get("Content-Type", "") if hd else "")
        if st != 200 or "html" not in ctype: continue
        p = Parser()
        try: p.feed(body.decode("utf-8", "replace"))
        except Exception: pass
        final = norm(final)
        if final in {pg["url"] for pg in pages}: continue
        pages.append({"url": final, "title": " ".join(p.title.split())})
        for kind, (href, text) in p.links:
            if href.startswith(("mailto:", "tel:", "javascript:", "#", "data:")): continue
            t = norm(urljoin(final, href))
            if not t.startswith("http"): continue
            refs.setdefault(t, []).append((final, kind, " ".join(text.split())[:80]))
            if kind == "link" and same(t) and t not in seen_pages and not t.lower().endswith(
                    (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".zip", ".mp4", ".docx", ".xlsx")):
                queue.append(t)
    results = {}
    for t in refs:
        st, chain, err, *_ = resolve(t, "HEAD"); results[t] = (st, chain, err)
        time.sleep(a.delay if same(t) else 0.2)
    faults = []
    for t, (st, chain, err) in results.items():
        for page, kind, text in refs[t]:
            if err or st is None or st >= 400:
                sev = "High" if same(t) or kind != "link" else "Medium"
                faults.append([sev, page, kind, text, t, st or err, "Remove the link or point it to a page that exists" if kind == "link" else "Upload the missing file or remove it from the page"])
            elif t.startswith("http://") and same(t):
                faults.append(["Low", page, kind, text, t, "http (not https)", "Change the address to start with https://"])
            elif len(chain) >= 2:
                faults.append(["Low", page, kind, text, t, f"{len(chain)} redirects", "Link straight to the final address"])
    titles = {}
    for p in pages:
        if not p["title"]: faults.append(["Low", p["url"], "page", "", p["url"], "no title", "Give the page a title"])
        titles.setdefault(p["title"], []).append(p["url"])
    for tt, us in titles.items():
        if tt and len(us) > 1:
            for u in us: faults.append(["Low", u, "page", tt[:80], u, "duplicate title", "Give each page its own title"])
    order = {"High": 0, "Medium": 1, "Low": 2}; faults.sort(key=lambda f: (order[f[0]], f[1]))
    days, cerr = cert_days(host)
    with open(f"{a.out}/faults.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["Importance", "On page", "Type", "Link text", "Address", "Result", "How to fix"]); w.writerows(faults)
    with open(f"{a.out}/pages.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["Page", "Title"]); [w.writerow([p["url"], p["title"]]) for p in pages]
    e = html.escape; n = lambda s: sum(1 for f in faults if f[0] == s)
    rows = "".join(f"<tr><td>{e(x[0])}</td><td>{e(x[1])}</td><td>{e(x[2])}</td><td>{e(x[3])}</td><td>{e(x[4])}</td><td>{e(str(x[5]))}</td><td>{e(x[6])}</td></tr>" for x in faults)
    cert = f"valid, expires in {days} days" if days is not None else f"problem: {e(cerr or '')}"
    rep = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Link check: {e(host)}</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;color:#222}}table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{border:1px solid #ccc;padding:4px;vertical-align:top;word-break:break-all}}th{{background:#f0f0f0}}</style></head><body>
<h1>Link check: {e(host)}</h1><p>Checked {datetime.date.today().isoformat()}: {len(pages)} pages, {len(results)} unique links and files.</p>
<p><b>{n('High')}</b> high, <b>{n('Medium')}</b> medium, <b>{n('Low')}</b> low importance. Security certificate: {cert}.</p>
<h2>Faults, most important first</h2><table><tr><th>Importance</th><th>On page</th><th>Type</th><th>Link text</th><th>Address</th><th>Result</th><th>How to fix</th></tr>{rows}</table>
<h2>Pages checked</h2><ol>{''.join(f'<li>{e(p["url"])}</li>' for p in pages)}</ol></body></html>"""
    open(f"{a.out}/report.html", "w").write(rep)
    print(f"pages={len(pages)} links={len(results)} faults={len(faults)} high={n('High')} cert={cert}")

if __name__ == "__main__":
    main()
