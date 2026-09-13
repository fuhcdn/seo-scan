import sys
sys.path.insert(0, "/opt/data/seo-audit-business/gates")
import gate_pipeline as gp
for name in [
    "FINAL4_AppleImprints_USD497_5ACTIONS_roadmapfix.pdf",
    "FINAL3_AppleImprints_USD497_5ACTIONS.pdf",
    "TestF_PASS_AppleImprints_USD497_5gate.pdf",
]:
    p = "/opt/data/seo-audit-business/" + name
    txt = gp.extract_visible_text_mature(open(p, "rb").read())
    print(f"===== {name} chars={len(txt)} =====")
    open("/opt/data/seo-audit-business/_review/" + name + ".txt", "w").write(txt)
print("done")