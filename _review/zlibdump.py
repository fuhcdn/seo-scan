import re, zlib, sys
p = "/opt/data/seo-audit-business/FINAL4_AppleImprints_USD497_5ACTIONS_roadmapfix.pdf"
pdf = open(p, "rb").read()
streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S)
print("num streams:", len(streams))
all_dec = b""
for i, s in enumerate(streams):
    try:
        d = zlib.decompress(s)
        all_dec += d + b"\n"
    except Exception as e:
        pass
# Extract text: look for Tj and TJ operators with parenthesized strings
texts = []
for m in re.finditer(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj", all_dec):
    texts.append(m.group(1))
# Try TJ array
print("Tj hits:", len(texts))
# Dump first decoded stream head to understand structure
print("=== first stream dec prefix ===")
first = None
for s in streams:
    try:
        first = zlib.decompress(s); break
    except: pass
print(first[:1500].decode("utf-8","replace") if first else "none")