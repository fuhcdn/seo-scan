import sys
sys.path.insert(0, "/opt/data/seo-audit-business/pipeline")
from pdf_scanner import extract_pdf_content

files = [
    "/opt/data/seo-audit-business/FINAL4_AppleImprints_USD497_5ACTIONS_roadmapfix.pdf",
    "/opt/data/seo-audit-business/FINAL3_AppleImprints_USD497_5ACTIONS.pdf",
    "/opt/data/seo-audit-business/TestF_PASS_AppleImprints_USD497_5gate.pdf",
    "/opt/data/seo-audit-business/FINAL_AppleImprints_USD497_ACCEPTED.pdf",
]
for name in files:
    data = extract_pdf_content(open(name, "rb").read())
    txt = data["text_str"]
    print(f"===== {name.split('/')[-1]} chars={len(txt)} streams={data['stream_hits']} =====")
    tag = name.split('/')[-1]
    open(f"/opt/data/seo-audit-business/_review/{tag}.txt", "w").write(txt)
print("done")