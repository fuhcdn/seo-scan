#!/usr/bin/env bash
# 快速檢查：清假social proof + 確認 landing 冇假見證
cd /opt/data/seo-audit-business/pipeline
echo "=== 檢查假 social proof 有冇漏網 ==="
for pat in "3,240" "98%" "陳生" "Kelly" "Marco" "+47%" "US\$50" "信用額"; do
  n=$(grep -rn "$pat" landing_page.html landing_page.template.html 2>/dev/null | wc -l)
  echo "[$pat] 出現 $n 次"
done
echo "=== 確認真後端 marker ==="
grep -c "DEMO_MODE = false" landing_page.html 2>/dev/null
grep -c "fetch('/api/scan'" landing_page.html 2>/dev/null