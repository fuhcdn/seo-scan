import re, zlib
f="/opt/data/seo-audit-business/FINAL4_AppleImprints_USD497_5ACTIONS_roadmapfix.pdf"
pdf=open(f,"rb").read()
streams=re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S)
out=b""
for s in streams:
    try: out+=zlib.decompress(s)+b"\n"
    except: pass
print("=== sample tokens (first 40) ===")
toks=re.findall(r"\(([^()\\]*)\)", out.decode("utf-8","replace"))
print(repr(toks[:40]))
print("=== search raw dec for 'Apple' === ")
for kw in [b"Apple", b"screen", b"print", b"Screen", b"Rollin", b"Embroidery"]:
    i = out.find(kw)
    print(kw, "at", i)
print("=== sample hex TJ region ===")
m = re.search(rb"\[.*?\]\s*TJ", out, re.S)
print(repr(m.group(0)[:500]) if m else "no array-TJ")
# count Tj and TJ operators
print("Tj count", out.count(b"Tj"), "TJ count", out.count(b"TJ"))