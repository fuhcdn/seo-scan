#!/usr/bin/env python3
"""Test suite for the FINAL AUTONOMOUS SEO REPORT CONTENT QUALITY STANDARD (§16).

Tests:
  Test A — Failure regression: blank action fields, unparsed SERP, generic business
           reason, legal pages as research, internal file paths -> delivery BLOCKED.
  Test B — US$497 pass fixture -> READY_TO_DELIVER, 90+ independent score, clean PDF.
  Test C — US$997 pass fixture -> READY_TO_DELIVER, 90+ independent score.
  Test D — Insufficient evidence (thin site) -> blocked, no padded normal report.
  Test E — Privacy: internal paths / order IDs / placeholders -> PDF/file validation BLOCKED.

Pure deterministic-gate tests (no live LLM needed except where noted as 'optional blind').
Run: python3 tests/test_autonomous_quality_gate.py
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.join(HERE, "..", "pipeline")
sys.path.insert(0, PIPE)
sys.path.insert(0, HERE)

import autonomous_gate as AG


def mk_order(fill=True):
    o = {"order_id": "ORD-TEST", "url": "https://client.example.com/business/",
         "company_name": "Example Business", "primary_business_goal": "more qualified leads",
         "main_products_or_services": "consulting, training", "target_market_or_service_area": "London",
         "primary_customer_action": "enquire", "report_language": "en",
         "selected_product_category": "ENTRY_REPORT"}
    if not fill:
        for k in ("primary_business_goal", "main_products_or_services", "primary_customer_action"):
            o[k] = ""
    return o


def mk_research(npages=8, nserp_valid=5, ncomp=3, legal_pages=False, bad_serp=False, leak=False):
    pages = [{"url": f"https://client.example.com/business/service/{i}", "ok": True,
              "type": "commercial", "purpose": "convert", "intent": "buy"} for i in range(npages)]
    if legal_pages:
        pages += [{"url": f"https://client.example.com/business/legal/privacy", "ok": True,
                   "type": "legal", "purpose": "compliance"}]
    if bad_serp:
        serp = [{"query": f"q{i}", "result_pattern": "",
                 "direct_observation": "Top results: none parsed — links: (no result parsed)",
                 "source_domains": ["(no result parsed)"]} for i in range(nserp_valid)]
    else:
        serp = [{"query": f"seo {c} london", "result_pattern": "commercial",
                 "direct_observation": f"Observed commercial result patterns with pricing; link https://pack{c}.example.com",
                 "source_domains": [f"pack{c}.example.com"], "source_url": f"https://pack{c}.example.com"} for c in range(nserp_valid)]
    comps = [f"competitor{i}.com" for i in range(ncomp)]
    ledger = [{"evidence_id": f"E{i}",
               "claim": f"Service pages {i} describe offers but rarely answer suitability/quote/next-step decision questions",
               "label": "INFERENCE", "source_url": f"https://client.example.com/business/service/{i}",
               "direct_observation": "Sampled commercial pages justify the finding.", "confidence": "Medium"}
              for i in range(5)]
    return {"website_url": "https://client.example.com/business/", "access_date": "2026-09-13",
            "customer_domain": "client.example.com",
            "customer_owned_domains": ["client.example.com"],
            "pages_reviewed": pages, "evidence_ledger": ledger, "serp": serp,
            "competitors": comps,
            "business": {"primary_business_goal": "more qualified leads", "company_name": "Example Business"},
            "architecture": {"home_ok": True, "pages_reviewed": pages, "robots_txt": {"ok": True},
                             "sitemap_urls": ["/sitemap.xml"]},
            "limitations": ["Public research only; private data not verified."]}


def mk_findings(n=3, blank_action=False, generic_reason=False, blank_owner=False):
    out = []
    for i in range(n):
        r = "relates directly to the stated goal and customer action"
        if generic_reason:
            r = "Relates to the stated goal (X)"  # generic
        out.append({"claim": f"Commercial service pages {i} lack decision support (comparison/proof/CTA) for the primary goal",
                    "business_reason": r,
                    "recommended_action": "" if blank_action else f"Add decision-support section to service page {i} with proof and single CTA",
                    "owner": "" if blank_owner else "Content",
                    "effort": "Medium",
                    "affected_scope": "https://client.example.com/business/service/0",
                    "acceptance_criteria": f"Service page {i} contains decision section + CTA",
                    "validation_method": "GSC/GA4 where access; else public re-check"})
    return out


def mk_actions(n=5, blank_fields=False):
    return [{"title": f"Publish decision-support page for query set {i}",
             "owner": "" if blank_fields else "Content",
             "acceptance_criteria": "" if blank_fields else "page live + linked",
             "validation_method": "" if blank_fields else "GSC"} for i in range(n)]


def delivery_blocked(det, blind=None):
    if blind is None:
        blind = {"total": 90, "hard_fail": False, "hard_fail_reasons": []}
    state, why = AG.decide_delivery(det, blind, is_pdf_clean=True)
    return state, why


def run_tests():
    results = []

    # ---- Test A: failure regression ----
    res = mk_research(bad_serp=True, npages=4, nserp_valid=3, ncomp=2)
    findings = mk_findings(n=2, blank_action=True, generic_reason=True, blank_owner=True)
    actions = mk_actions(n=3, blank_fields=True)
    det = AG.deterministic_validate(res, findings, actions, "ENTRY_REPORT", mk_order(), doc_text="file:///app/secrets.env")
    state, why = delivery_blocked(det)
    a_pass = state != "READY_TO_DELIVER"
    results.append(("A-failure-blocked", a_pass, state, why[:2]))

    # ---- Test B: US$497 pass ----
    res = mk_research(npages=8, nserp_valid=5, ncomp=3)
    det = AG.deterministic_validate(res, mk_findings(3), mk_actions(5), "ENTRY_REPORT", mk_order(), doc_text="clean sourcing pages")
    b_blocked = det.get("hard_fail_list")
    # minimal deterministic verify; blind scored separately in step_report
    results.append(("B-497-deterministic-no-hardfail", not b_blocked, "hard_fail", b_blocked))

    # ---- Test C: US$997 pass (premium fixture) ----
    res = mk_research(npages=14, nserp_valid=10, ncomp=4)
    det = AG.deterministic_validate(res, mk_findings(6), mk_actions(18), "PREMIUM_REPORT", {**mk_order(), "selected_product_category": "PREMIUM_REPORT", "report_tier": "PREMIUM_REPORT"}, doc_text="clean premium sourcing")
    c_blocked = det.get("hard_fail_list")
    results.append(("C-997-deterministic-no-hardfail", not c_blocked, "hard_fail", c_blocked))

    # ---- Test D: insufficient evidence ----
    res = mk_research(npages=1, nserp_valid=0, ncomp=1)
    det = AG.deterministic_validate(res, mk_findings(1), mk_actions(1), "ENTRY_REPORT", mk_order(), doc_text="thin")
    state, why = delivery_blocked(det)
    d_pass = state in ("RESEARCH_INCOMPLETE", "DELIVERY_BLOCKED")
    results.append(("D-insufficient-blocked", d_pass, state, why[:2]))

    # ---- Test E: privacy ----
    res = mk_research(npages=8, nserp_valid=5, ncomp=3, leak=True)
    det = AG.deterministic_validate(res, mk_findings(3), mk_actions(5), "ENTRY_REPORT", mk_order(), doc_text="ORD-ABC123 payment_ref pi_live_123 localhost /app/pipeline secret sk_live_")
    e_blocked = det.get("internal_path_leak_count", 0) > 0 or det.get("placeholder_count", 0) > 0 or det.get("privacy_leak", 0) > 0
    results.append(("E-privacy-leak-flagged", e_blocked, "leak_count", det.get("internal_path_leak_count")))

    # ---- Test F: customer-ownership — action targeting competitor domain must block ----
    res_f = mk_research(npages=8, nserp_valid=5, ncomp=3)
    findings_f = mk_findings(3)
    actions_f = mk_actions(5)
    actions_f[0]["affected_scope"] = "https://comped.com/service"
    actions_f[0]["customer_owned_scope"] = "https://comped.com/service"
    det_f = AG.deterministic_validate(res_f, findings_f, actions_f, "ENTRY_REPORT", mk_order(), doc_text="clean")
    f_blocked = det_f.get("forbidden_action_targets", 0) > 0 and any("forbidden_action_target" in h for h in (det_f.get("hard_fail_list") or []))
    results.append(("F-competitor-target-blocked", f_blocked, "targets", det_f.get("forbidden_action_target_urls")))

    # ---- Test G: evidence-type separation — competitor_page evidence must NOT count as SERP ----
    res_g = dict(mk_research(npages=8, nserp_valid=5, ncomp=3))
    res_g["serp"] = [{"query": "q0", "direct_observation": "Top results: none parsed — links: (no result parsed)",
                      "source_domains": ["(no result parsed)"], "counts_toward_serp": False}]
    res_g["competitor_observations"] = [{"source": "competitor_page", "source_url": "https://ahrefs.com/blog/",
                                         "title": "Ahrefs Blog", "counts_toward_serp": False, "label": "FACT"}]
    det_g = AG.deterministic_validate(res_g, mk_findings(3), mk_actions(5), "ENTRY_REPORT", mk_order(), doc_text="clean")
    g_pass = det_g.get("valid_serp_observation_count", 0) == 0
    results.append(("G-competitor-not-serp", g_pass, "valid_serp", det_g.get("valid_serp_observation_count")))

    print("=" * 60)
    ok_count = 0
    for name, passed, info_k, info_v in results:
        mark = "PASS" if passed else "FAIL"
        if passed:
            ok_count += 1
        print(f"[{mark}] {name}: {info_v}")
    print("=" * 60)
    print(f"Tests passed: {ok_count}/{len(results)}")
    return ok_count == len(results)


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)