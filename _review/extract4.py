import sys
sys.path.insert(0, "/opt/data/seo-audit-business/_review/pypdf_src")
from pypdf import PdfReader
files = [
    "FINAL4_AppleImprints_USD497_5ACTIONS_roadmapfix.pdf",
    "FINAL3_AppleImprints_USD497_5ACTIONS.pdf",
    "FINAL_AppleImprints_USD497_ACCEPTED.pdf",
    "GATE5_FINAL2_AppleImprints_USD497.pdf",
    "TestF_PASS_AppleImprints_USD497_5gate.pdf",
]
for name in files:
    r = PdfReader("/opt/data/seo-audit-business/" + name)
    text = "\n".join((pg.extract_text() or "") for pg in r.pages)
    print(f"===== {name} pages={len(r.pages)} chars={len(text)} =====")
    open("/opt/data/seo-audit-business/_review/" + name + ".txt", "w").write(text)
print("done")