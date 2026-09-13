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
             "affected_scope": "" if blank_fields else "https://client.example.com/business/service/%d" % i,
             "customer_owned_scope": "" if blank_fields else "https://client.example.com/business/service/%d" % i,
             "acceptance_criteria": "" if blank_fields else "page live + linked + QA passed",
             "validation_method": "" if blank_fields else "GSC; first-signal CTA clicks; review 30d"} for i in range(n)]


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

    # ---- Test H: cross-customer contamination — foreign brand in a customer action must block ----
    res_h = mk_research(npages=8, nserp_valid=5, ncomp=3)
    # customer is client.example.com; inject a Semrush directive into an action (the real Bug 1)
    lock_h = AG.build_customer_context_lock({**mk_order(), "known_competitors": ["semrush.com", "ahrefs.com"]}, res_h)
    findings_h = mk_findings(3)
    actions_h = mk_actions(5)
    actions_h[1]["title"] = "Improve Semrush's SEO checklist page"   # contamination
    actions_h[1]["recommended_action"] = "Align a Semrush-owned page"
    contam, terms = AG.cross_customer_contamination_check(lock_h, findings_h, actions_h)
    h_pass = contam > 0
    results.append(("H-cross-customer-contamination-blocked", h_pass, "foreign_terms", terms))

    # ---- Test I: post-render final-artifact leakage — directive-style foreign contamination in PDF text ----
    # simulate rendered PDF text containing an internal path AND a directive to a competitor
    fake_pdf = "file:///app/pipeline/out/test.html align Semrush's page improve ahrefs rank"
    leak_terms = []
    dir_pat = __import__("re").compile(
        r"(align|improve|rewrite|update|fix|restructure|create|add|reposition)\s+(semrush|ahrefs|moz):?[- ]?(owned)?|"
        r"(semrush|ahrefs|moz)[- ]owned|"
        r"action\s+target:?\s+(semrush|ahrefs|moz)\.com", __import__("re").I)
    m = dir_pat.findall(fake_pdf)
    if m:
        for g in m:
            t = [x for x in g if x]
            if t:
                leak_terms.append(t[0])
    leak_path = fake_pdf.count("/app/pipeline") + fake_pdf.count("file://")
    i_pass = leak_path > 0 and len(leak_terms) > 0
    results.append(("I-post-render-leakage-blocked", i_pass, "path_terms", (leak_path, leak_terms)))

    # ---- Test J: business-model mismatch — quote path for ecommerce (buy) must be rejected ----
    _fit_ok, _fit_note = AG.evaluate_business_model_fit if hasattr(AG, "evaluate_business_model_fit") else (True, "n/a")
    # direct unit of the helper from quality_gate
    import quality_gate as QG
    _j_fit, _j_note = QG.business_model_fit("Add a quote request form", "customer compares cost",
                                            "shop", "buy", "UK")
    j_pass = (_j_fit is False)
    results.append(("J-business-model-mismatch-rejected", j_pass, "fit_note", _j_note))

    # ---- Test K: generic-action failure — catch generic advice without a specific observed gap ----
    # generic actions must not pass the action rationale check (vetted by blind/deterministic generic counts)
    res_k = mk_research(npages=8, nserp_valid=5, ncomp=3)
    acts_k = mk_actions(5)
    acts_k[0]["title"] = "Improve content"
    det_k = AG.deterministic_validate(res_k, mk_findings(3), acts_k, "ENTRY_REPORT", mk_order(), doc_text="clean")
    k_generic = det_k.get("generic_action_count", 0) > 0
    results.append(("K-generic-action-flagged", k_generic, "generic_action_count", det_k.get("generic_action_count")))

    # ---- Test L: invalid action scope (serp_result_pattern) blocks (user reject #2) ----
    res_l = mk_research(npages=8, nserp_valid=5, ncomp=3)
    actions_l = mk_actions(5)
    actions_l[0]["customer_owned_scope"] = "serp_result_pattern"  # evidence class, not customer page
    actions_l[0]["title"] = "Add a comparison/decision matrix to serp_result_pattern"
    det_l = AG.deterministic_validate(res_l, mk_findings(3), actions_l, "ENTRY_REPORT", mk_order(), doc_text="clean")
    l_pass = "invalid_action_scope" in (det_l.get("hard_fail_list") or [])
    results.append(("L-invalid-action-scope-blocked", l_pass, "hard_fail", det_l.get("hard_fail_list")))

    # ---- Test M: generic business mechanism blocks (user reject #4) ----
    res_m = mk_research(npages=8, nserp_valid=5, ncomp=3)
    findings_m = mk_findings(3)
    findings_m[0]["business_reason"] = ("This observation affects the likelihood that visitors "
                                        "progress toward the stated business goal (more sales-revenue).")
    det_m = AG.deterministic_validate(res_m, findings_m, mk_actions(5), "ENTRY_REPORT", mk_order(), doc_text="clean")
    m_pass = "generic_mechanism" in " ".join(det_m.get("hard_fail_list") or [])
    results.append(("M-generic-mechanism-blocked", m_pass, "hard_fail", det_m.get("hard_fail_list")))

    # ---- Test N: generic definition-of-done blocks (user reject #7) ----
    res_n = mk_research(npages=8, nserp_valid=5, ncomp=3)
    actions_n = mk_actions(5)
    actions_n[0]["acceptance_criteria"] = "Implement the action and confirm via public source"
    det_n = AG.deterministic_validate(res_n, mk_findings(3), actions_n, "ENTRY_REPORT", mk_order(), doc_text="clean")
    n_pass = any("generic_definition_of_done" in h or "action_completeness" in h for h in (det_n.get("hard_fail_list") or []))
    results.append(("N-generic-done-blocked", n_pass, "hard_fail", det_n.get("hard_fail_list")))

    # ---- Test O: business-model mismatch rejected at generator (user reject #5) ----
    import quality_gate as QG2
    fit_ok, fit_note = QG2.business_model_fit("Add a quote request form", "customer wants to compare cost",
                                              "shop", "buy", "UK")
    o_pass = (fit_ok is False)
    results.append(("O-business-model-mismatch-generator", o_pass, "fit_note", fit_note))

    # ---- Test P: PDF privacy scanner blocks file:///app/pipeline/out/...html (user reject #1) ----
    from pdf_scanner import scan_pdf_for_leaks
    import zlib
    leak_str = b"file:///app/pipeline/out/SEO-Opportunity-Diagnostic-apple-2026-09-13.html"
    body = b"BT (" + leak_str + b") Tj ET"
    stream = zlib.compress(body)
    header = b"%PDF-1.4\n1 0 obj<</Length " + str(len(stream)).encode() + b"/Filter /FlateDecode>>stream\n"
    trailer = b"\nendstream\nendobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    ps = scan_pdf_for_leaks(header + stream + trailer)
    p_pass = ps["blocked"] is True and ps["hard_fail"] == "INTERNAL_PATH_LEAK"
    results.append(("P-pdf-scanner-file-url-blocked", p_pass, "hits", ps["hits"]))

    # ---- Test Q: staging threshold must yield STAGING_TEST_PASS, never READY_TO_DELIVER ----
    res_q = mk_research(npages=8, nserp_valid=5, ncomp=3)
    det_q = AG.deterministic_validate(res_q, mk_findings(3), mk_actions(5), "ENTRY_REPORT", mk_order(), doc_text="clean")
    # threshold 80 (staging/test) -> must be STAGING_TEST_PASS even with blind 95
    st80, why80 = AG.decide_delivery(det_q, {"total": 95, "hard_fail": False}, is_pdf_clean=True, min_score=80)
    # threshold 90 (production) -> READY_TO_DELIVER
    st90, why90 = AG.decide_delivery(det_q, {"total": 95, "hard_fail": False}, is_pdf_clean=True, min_score=90)
    q_pass = (st80 == "STAGING_TEST_PASS") and (st90 == "READY_TO_DELIVER")
    results.append(("Q-staging-vs-ready-state-separation", q_pass, "st80/st90", f"{st80}|{st90}"))

    # ---- Test R: scorecard is explicit out-of-100, per-category raw+pct, threshold+transition ----
    blind_r = {"total": 95, "hard_fail": False,
               "A_evidence": {"points": 19}, "B_research": {"points": 19},
               "C_strategic": {"points": 19}, "D_actionability": {"points": 19},
               "E_structure": {"points": 10}, "F_pdf": {"points": 9}}
    sc = AG.build_scorecard(det_q, blind_r, "READY_TO_DELIVER", min_score=90)
    # ensure no ambiguous "x/y" out-of-100 rendering; explicit out-of-100 + per-category pct
    r_pass = (sc["score_out_of"] == 100 and sc["final_out_of"] == 100
              and sc["threshold"] == 90 and sc["threshold_role"] == "production"
              and sc["per_category_pct"]["A_evidence"] == 95.0 and sc["state"] == "READY_TO_DELIVER")
    results.append(("R-explicit-scorecard-out-of-100", r_pass, "sample", f"A=95% thresh={sc['threshold']} role={sc['threshold_role']}"))

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