import re, zlib
files = [
    "FINAL4_AppleImprints_USD497_5ACTIONS_roadmapfix.pdf",
    "FINAL3_AppleImprints_USD497_5ACTIONS.pdf",
    "TestF_PASS_AppleImprints_USD497_5gate.pdf",
]
def dec(p):
    pdf = open(p,"rb").read()
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S)
    out=b""
    for s in streams:
        try: out += zlib.decompress(s)+b"\n"
        except: pass
    return out
for f in files:
    d = dec("/opt/data/seo-audit-business/"+f)
    t = d.decode("utf-8","replace")
    # find parenthesized text tokens
    toks = re.findall(r"\(([^()\\]{2,})\)", t)
    join = " ".join(toks)
    print(f"===== {f}: stream_bytes={len(d)} tokens={len(toks)} =====")
    for kw in ["Apple Imprints","screen-printing","90-Day","DO NOW","VALIDATE FIRST","Days 31-60","ACT-004","route","AppleImprints","Founding finding","Finding 1","get-a-quote"]:
        print(f"  [{kw}] -> {join.count(kw)}")
    open("/opt/data/seo-audit-business/_review/"+f+".tokens.txt","w").write(join)