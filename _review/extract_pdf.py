import sys
try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader
files = [
    "/opt/data/seo-audit-business/FINAL4_AppleImprints_USD497_5ACTIONS_roadmapfix.pdf",
    "/opt/data/seo-audit-business/FINAL3_AppleImprints_USD497_5ACTIONS.pdf",
    "/opt/data/seo-audit-business/TestF_PASS_AppleImprints_USD497_5gate.pdf",
]
for name in files:
    r = PdfReader(name)
    n = len(r.pages)
    text = "\n".join((p.extract_text() or "") for p in r.pages)
    print(f"===== {name.split('/')[-1]} pages={n} chars={len(text)} =====")
    out = "/opt/data/seo-audit-business/_review/" + name.split('/')[-1] + ".txt"
    open(out, "w").write(text)
print("done")