#!/usr/bin/env python3
"""Scoring determinism tests — same signals = same score (owner requirement).

Run: .venv/bin/python tests/test_scoring_determinism.py
"""
import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "pipeline"))
import seo_crawler as SC  # noqa: E402

RESULTS = []
def check(n, c, i=""):
    RESULTS.append((n, bool(c), i))
    print(f"[{'PASS' if c else 'FAIL'}] {n}: {i}")

# 1. rule-based fixes are deterministic: same input dict -> identical output
sig = {"url": "https://example-firm.com", "title": "x" * 90, "h1_count": 0,
       "img_count": 10, "img_alt_count": 2, "meta_desc_len": 190}
srv = {"ttfb_ms": 250, "http_status": 200, "compression": None}
r1 = SC.rule_based_fixes({"signals": sig, "server_signals": srv, "robots": {}, "crawl_errors": []})
r2 = SC.rule_based_fixes({"signals": sig, "server_signals": srv, "robots": {}, "crawl_errors": []})
s1 = SC._estimate_score(SC._normalize_fix_list(r1))
s2 = SC._estimate_score(SC._normalize_fix_list(r2))
check("1-rule-fixes-deterministic", r1 == r2, f"{len(r1)} fixes")
check("2-estimate-score-deterministic", s1 == s2, f"score={s1}")

# 3. score is bounded 0-100 for extreme inputs
fixes_extreme = [{"priority": "urgent"}] * 10
s3 = SC._estimate_score(SC._normalize_fix_list(fixes_extreme))
check("3-score-bounded", 0 <= s3 <= 100, f"10 urgent → {s3}")

# 4. clean site → high score (no fixes = 100)
s4 = SC._estimate_score(SC._normalize_fix_list([]))
check("4-clean-site-100", s4 == 100, f"empty fixes → {s4}")

# 5. AI scorer uses temperature 0 (grep source — deterministic config)
src = open(os.path.join(_HERE, "..", "pipeline", "seo_crawler.py"), encoding="utf-8").read()
no_rand_temp = '"temperature": 0.2' not in src and '"temperature": 0,' in src
check("5-ai-temperature-zero", no_rand_temp, "temperature 0 in ai_score attempts")

# 6. TTFB median sampling present in run()
ttfb_median_present = "ttfb_samples_ms" in src and "_ttfb_median" in src
check("6-ttfb-median-sampling", ttfb_median_present, "3-sample median in run()")

# 7. rule weight table is the documented 15/8/4/2 (stable contract)
s_a = SC._estimate_score(SC._normalize_fix_list([{"priority": "urgent"}]))
s_b = SC._estimate_score(SC._normalize_fix_list([{"priority": "high"}]))
s_c = SC._estimate_score(SC._normalize_fix_list([{"priority": "medium"}]))
s_d = SC._estimate_score(SC._normalize_fix_list([{"priority": "low"}]))
check("7-weight-contract", (s_a, s_b, s_c, s_d)  == (82, 90, 95, 98), f"urgent={s_a} high={s_b} med={s_c} low={s_d}")

ok = sum(1 for _, p, _ in RESULTS if p)
print("=" * 60)
print(f"Scoring determinism tests: {ok}/{len(RESULTS)}")
sys.exit(0 if ok == len(RESULTS) else 1)
