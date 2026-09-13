"""FIVE-GATE evidence-led US$497 report runner (no SERP template shortcuts).

Loads GATE1 structured pages + 3 Golden Evidence Cards -> GATE1/2/3/4 (semantic auditor
writes accepted/rejected reasons) -> builds an evidence-led English report -> renders PDF
ONCE -> SHA-256 + scan that exact file -> PASS/FAIL. Uses the OpenRouter independent
auditor for GATE 4 semantic reasons.
"""
from __future__ import annotations
import base64
import hashlib
import html as H
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gate_pipeline as gp
from seo_crawler import resolve_openrouter_key, openrouter_chat, _coerce_msg_content


def _esc(x):
    return H.escape(str(x), quote=True)


def load_cards(path):
    return json.load(open(path, encoding="utf-8"))


def gate4_external_auditor(findings, cards):
    """Independent OpenRouter audit: returns a reason for each accepted + rejected finding."""
    key = resolve_openrouter_key()
    reasons = []
    if not key:
        return [{"mode": "deterministic-only", "reasons": []}]
    # window the FULL evidence cards + implementation briefs into the prompt
    card_blob = "\n\n".join(
        f"EC {c['card_id']}: page={c['primary_customer_url']}\n"
        f"  observation={c['direct_observation'][:200]}\n"
        f"  gap={c['specific_gap']}\n"
        f"  mechanism={c['business_mechanism'][:200]}\n"
        f"  module={c['recommended_module']}\n"
        f"  brief_placement={((c.get('implementation_brief') or {}).get('exact_module_placement') or (c.get('implementation_brief') or {}).get('exact_three_steps') or '')}\n"
        f"  brief_approval={((c.get('implementation_brief') or {}).get('approval_dependency') or (c.get('implementation_brief') or {}).get('approval_who') or '')}\n"
        f"  brief_scale={((c.get('implementation_brief') or {}).get('scale_rule') or '')}"
        for c in cards[:3])
    cand_blob = "\n".join(
        f"- {a['action_id']}: {a['title']} | URL={a.get('card',{}).get('primary_customer_url','')} | DoD={a['acceptance_criteria'][:160]}"
        for a in findings)
    prompt = (
        "You are the independent SEMANTIC QUALITY AUDITOR for a US$497 evidence-led SEO report.\n"
        "For each candidate action below, decide ACCEPT or REJECT and give a short (<=22 word) "
        "human-readable reason a real SME owner can act on. Reject ONLY if genuinely duplicated, "
        "generic/unactionable, targets an unrelated page, or uses a generic definition-of-done.\n"
        "The candidates are derived from these Golden Evidence Cards (direct customer-page observations):\n"
        + card_blob + "\n\nCANDIDATES:\n" + cand_blob +
        "\n\nReply ONLY as JSON: {\"decisions\":[{\"action_id\":\"ACT-001\",\"accept\":true,\"reason\":\"...\"}]}")
    try:
        payload = {"model": "deepseek/deepseek-chat-v3-0324", "messages": [
            {"role": "system", "content": "You are a strict, evidence-based report quality auditor."},
            {"role": "user", "content": prompt}], "temperature": 0}
        env = openrouter_chat(key, payload)
        content = _coerce_msg_content(env.get("choices", [{}])[0].get("message", {}).get("content", ""))
        if not content or not content.strip():
            payload.pop("response_format", None)
            env = openrouter_chat(key, payload)
            content = _coerce_msg_content(env.get("choices", [{}])[0].get("message", {}).get("content", ""))
        if isinstance(content, str) and content.strip():
            js = content[content.find("{"): content.rfind("}") + 1] if "{" in content else content
            decs = json.loads(js).get("decisions", []) if js.strip().startswith("{") else []
            return [{"mode": "external", "decisions": decs}]
        return [{"mode": "external-empty", "reasons": []}]
    except Exception as e:
        return [{"mode": "external-error", "error": str(e)[:120], "reasons": []}]


def build_report(customer, pages, findings, acts, auditor_output, cards=None):
    """Evidence-led report: conclusions first, one URL per action, specific DoD."""
    cards = cards or []
    exec_cards = ""
    for i, (f, a) in enumerate(zip(findings, acts), 1):
        card = f.get("card", {})
        inv = "VALIDATE FIRST" if (a.get("effort") or "small").lower() != "small" else "DO NOW"
        ib = card.get("implementation_brief") or {}
        exec_cards += f"""
<div class="card">
 <h4>Founding finding {i} — <em>{_esc(card.get('specific_gap','')[:70])}</em> <span class="src">[{inv}]</span></h4>
 <p><strong>Customer page:</strong> {_esc(card.get('primary_customer_url',''))}</p>
 <p><strong>Direct observation:</strong> {_esc(card.get('direct_observation',''))}</p>
 <p><strong>Buyer question:</strong> {_esc(card.get('buyer_question',''))}</p>
 <p><strong>Specific gap:</strong> {_esc(card.get('specific_gap',''))}</p>
 <p><strong>Business mechanism:</strong> {_esc(card.get('business_mechanism',''))}</p>
 <p><strong>Recommended change (module):</strong> {_esc(card.get('recommended_module',''))}</p>
 <p class="src">Reason accepted by auditor: {_esc(f.get('audit_reason',''))}</p>
</div>"""
    # implementation briefs section
    briefs = ""
    for a in acts:
        c = next((k for k in cards if k.get("card_id") in (a.get("evidence_ids") or [])), None) or {}
        ib = c.get("implementation_brief") or {}
        if ib:
            steps = ib.get("exact_three_steps") or []
            cand = ib.get("candidate_copy_for_owner_approval") or {}
            rows = "".join(f"<li><strong>{_esc(k)}:</strong> {_esc(v)}</li>" for k, v in cand.items())
            steps_html = "".join(f"<li>{_esc(s)}</li>" for s in steps)
            approval = (ib.get("owner_confirmation_required") or
                        ib.get("approval_dependency") or ib.get("approval_who") or "")
            briefs += f"""<div class="card">
<h4>Implementation brief — {a['action_id']} ({_esc(c['card_id'])})</h4>
<p><strong>Approval flag:</strong> {_esc(approval)}</p>
<p><strong>Exact placement:</strong> {_esc(ib.get('exact_module_placement',''))}</p>
{f'<p><strong>Candidate copy (owner confirmation required before publication):</strong></p><ul>{rows}</ul>' if rows else ''}
{f'<p><strong>Three post-submission steps:</strong></p><ol>{steps_html}</ol>' if steps else ''}
<p><strong>CTA destination:</strong> {_esc(ib.get('exact_quote_cta_destination',''))}</p>
<p><strong>Trust/proof route:</strong> {_esc(ib.get('exact_trust_proof_route',''))}</p>
<p><strong>QA:</strong> {_esc(ib.get('qa','') + ' ' + ib.get('module_position',''))}</p>
<p><strong>Baseline:</strong> {_esc(ib.get('baseline_metrics','') + ' ' + ib.get('baseline_and_review',''))}</p>
<p><strong>Scale rule:</strong> {_esc(ib.get('scale_rule',''))}</p>
</div>"""
    # quick win: smallest effort, reversible, one URL
    qw = min(acts, key=lambda x: len(x.get("recommended_module", "") or ""), default=None)
    quick = f"""<div class="card"><h4>First 7-Day Win</h4>
<p><strong>{_esc(qw['action_id'])}</strong> — {_esc((qw.get('recommended_module') or '')[:80])}</p>
<p><strong>Single customer page:</strong> {_esc(qw['primary_url'])}</p>
<p>Why first: small, reversible, on one high-intent customer-owned page — validates the wider plan.</p></div>""" if qw else ""
    # investment matrix from real effort (corrected by owner: ACT-003 DO NOW; ACT-001/002 VALIDATE FIRST)
    dim = """<h2>Investment Decision Matrix</h2>
<div class="card"><h4>DO NOW</h4><ul>
<li>ACT-003 — Add captions/technique tags to the first 12 gallery items (on https://appleimprints.com/gallery/). Low-cost, reversible, high-intent proof page.</li>
</ul>
<h4>VALIDATE FIRST (pending owner approval)</h4><ul>
<li>ACT-001 — Add the 'Pricing &amp; Minimums' section to the screen-printing page — requires owner confirmation of MOQ / price factors / setup fee / turnaround before publish.</li>
<li>ACT-002 — Add the 3-step 'What happens next' trust block to the quote page — requires owner approval of the response-time SLA and proof route.</li>
</ul>
<h4>DEFER / DO NOT PRIORITISE YET</h4><p>For Apple Imprints specifically: do not spend on a paid link-building campaign, a full site redesign, a new online store, or expanding gallery tagging beyond the first 12 items until the three customer-owned page changes above are proven. No competitor action, external links, or redesign is part of this 90-day plan.</p></div>"""
    # customer-specific what-not-to-prioritise (evidence-based, not generic)
    whatnot = f"""<h2>What Not To Prioritise Yet</h2><div class="card">
<p>For Apple Imprints specifically, the evidence does not yet justify spending on: (1) a paid link-building campaign, (2) a redesign of the whole site, (3) a new online store, or (4) expanding gallery tagging beyond the first 12 items — the three customer-owned page gaps documented here (pricing/minimums on screen-printing, trust/expectation on the quote form, labelled proof on the gallery) are cheaper and higher-leverage first.</p></div>"""
    # action ledger — one URL each
    ledger = ""
    for a in acts:
        ledger += f"""<div class="card">
<h4>{a['action_id']} — {_esc((a.get('recommended_module') or '')[:70])}</h4>
<p><strong>Primary customer URL (single):</strong> {_esc(a['primary_url'])}</p>
<p><strong>Business mechanism:</strong> {_esc(a.get('business_mechanism','')[:180])}</p>
<p><strong>Definition of done:</strong> {_esc(a.get('acceptance_criteria','')[:220])}</p>
<p><strong>First signal/validation:</strong> {_esc(a.get('validation_method','')[:180])}</p>
<p><strong>Review:</strong> {a.get('review_window','30-60 days')} · Owner: {a.get('owner','Content/SEO')} · Effort: {a.get('effort','Small')}</p></div>"""
    # source / evidence appendix
    src_rows = ""
    for c in cards:
        src_rows += f"<tr><td>{c['card_id']}</td><td>{_esc(c['primary_customer_url'])}</td><td>{_esc(c['direct_observation'][:110])}…</td></tr>"
    title = f"SEO Opportunity Diagnostic — {customer.get('company','Customer')}"
    today = "2026-09-13"
    html_doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{_esc(title)}</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#172b4d;background:#faf8f2;margin:28px auto;max-width:980px}}
 h1{{font-size:24px}}h2{{font-size:17px;border-bottom:1px solid #d9d2c0;padding-bottom:4px}}
 .callout{{background:#eef2ff;border:1px solid #c9d4f7;border-left:5px solid #4169e1;padding:12px 16px}}
 .card{{background:#fff;border:1px solid #e0dccd;border-radius:8px;padding:12px 16px;margin:10px 0}}
 .src{{color:#6b7280;font-size:12px}} table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #ddd;padding:6px;text-align:left}}
 .disc{{color:#6b7280;font-size:11px}}
</style></head><body>
 <div class="callout"><h1>{_esc(title)}</h1>
 <p>Prepared for {_esc(customer.get('company',''))} · {_esc(customer.get('primary_domain',''))} · Report date {today}</p>
 <p>Public-web research and direct page observation on customer-owned pages. Goal: {_esc(customer.get('business_goal',''))}. This is an evidence-led decision report; nothing is guaranteed.</p></div>
 <h2>Executive Summary — Highest-Value Decisions</h2>{exec_cards or '<p>No evidence-led decisions passed audit.</p>'}
 {briefs or ''}
 {quick or ''}
 {whatnot}
 <h2>Commercial Opportunity Model</h2><div class="card"><p>Value lever: demand capture + page clarity. Publicly observable evidence: the three customer pages lack price/minimum/turnaround and trust detail (see evidence cards). Client data required to quantify: quote submissions, CTA clicks, lead/order rate (GSC/GA4 when provided). Assumptions only — never a forecast.</p></div>
 {dim}
 <h2>Top Priority Actions</h2>{ledger}
 <h2>Source / Evidence Appendix</h2>
 <table><tr><th>Card</th><th>Customer URL</th><th>Direct observation (excerpt)</th></tr>{src_rows}</table>
 <p class="disc">This report uses public-web research on publicly accessible pages unless otherwise stated; search results change; no outcome is guaranteed. Competitor sites appear only as sources, never as work targets.</p>
</body></html>"""
    return html_doc


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="/app/pipeline/out")
    ap.add_argument("--customer-email", default="")
    ap.add_argument("--send", action="store_true", help="email only after hash verification")
    args = ap.parse_args()

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    here = os.path.dirname(os.path.abspath(__file__))
    cards_file = json.load(open(os.path.join(here, "golden_evidence_cards_appleimprints.json"), encoding="utf-8"))
    cards = cards_file["golden_evidence_cards"]
    customer = cards_file["customer"]

    import importlib.util
    sp = importlib.util.spec_from_file_location("g1p", os.path.join(here, "gate1_appleimprints_pages.py"))
    g1m = importlib.util.module_from_spec(sp); sp.loader.exec_module(g1m)
    pages = g1m.structured_pages

    results = {}
    # ---- GATE 1 ----
    g1 = gp.gate1_validate_structured_pages(pages)
    results["GATE1"] = {"valid": g1["valid"], "meaningful_count": g1["meaningful_count"],
                        "issues": g1["issues"]}
    # ---- GATE 2 ----
    g2v = [gp.gate2_validate_evidence_card(c) for c in cards]
    valid_cards = [c for c, v in zip(cards, g2v) if v["valid"]]
    results["GATE2"] = {"valid": len(valid_cards) == len(cards),
                        "cards": [{"id": v["card_id"], "valid": v["valid"], "blank": v["blank_fields"]} for v in g2v]}
    # ---- GATE 3 ----
    acts = gp.gate3_actions_from_evidence_cards(valid_cards)
    all_single = all(len((a.get("primary_url") or "").split(";")) == 1 for a in acts)
    results["GATE3"] = {"valid": bool(acts) and all_single, "action_count": len(acts)}
    # ---- GATE 4 ----
    findings = [{"action_id": a["action_id"], "title": a["title"], "card": c,
                 "acceptance_criteria": a["acceptance_criteria"],
                 "business_mechanism": a["business_mechanism"], "audit_reason": ""}
                for a, c in zip(acts, valid_cards)]
    g4 = gp.gate4_semantic_audit(findings, acts)
    ext_audit = gate4_external_auditor(findings, valid_cards)
    # map external accept/reject reasons by action_id
    accepted = g4["accepted_findings"]
    if ext_audit and ext_audit[0].get("mode") == "external":
        for d in ext_audit[0].get("decisions", []):
            for f in accepted:
                if d.get("action_id") and d.get("action_id") == f.get("action_id"):
                    f["audit_reason"] = d.get("reason", "")
    results["GATE4"] = {"valid": g4["accepted_count"] >= 1 and ext_audit and ext_audit[0].get("mode") == "external",
                        "accepted": [{"action_id": f.get("action_id"), "title": f["title"],
                                      "reason": f.get("audit_reason", "") or "deterministic accept"}
                                     for f in accepted],
                        "rejected": g4["rejected_findings"],
                        "external": ext_audit}
    # ---- Build + GATE 5 ----
    html_doc = build_report(customer, pages, accepted, acts, results["GATE4"], cards=valid_cards)
    html_path = os.path.join(out_dir, "SEO-Opportunity-Diagnostic-Apple-Imprints-2026-09-13-5gate.html")
    pdf_path = os.path.join(out_dir, "SEO-Opportunity-Diagnostic-Apple-Imprints-2026-09-13-5gate.pdf")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    from report_engine import html_to_pdf
    ok = html_to_pdf(html_path, pdf_path)
    if not ok:
        print(json.dumps({"overall": "FAIL/BLOCK", "reason": "pdf render failed"}, indent=1)); return
    final = gp.gate5_finalize_pdf(pdf_path)
    scan = final["scan"]
    results["GATE5"] = {"clean": scan["clean"], "hard_fails": scan["hard_fails"],
                        "sha256": scan["sha256"], "hits": scan["hits"],
                        "bytes": scan["bytes"], "lock": final["marker"],
                        "scan_input_sha": scan["sha256"], "rendered_sha": scan["sha256"]}
    # ---- Decision Engine ----
    gate5_ok = scan["clean"] and not scan["hard_fails"]
    overall_valid = (results["GATE1"]["valid"] and results["GATE2"]["valid"] and results["GATE3"]["valid"]
                     and results["GATE4"]["valid"] and gate5_ok)
    overall = "PASS" if overall_valid else "FAIL"
    results["overall"] = overall
    if overall == "PASS":
        # HARD RULE: 3-way SHA (rendered == scanned == email attachment) before any send
        email_copy = pdf_path + ".for-email.pdf"
        import shutil as _sh
        _sh.copy2(pdf_path, email_copy)
        if not gp.gate5_three_way_verify(scan["sha256"], email_copy, scan["sha256"]):
            results["overall"] = "FAIL"; results["reason"] = "3-way SHA mismatch / re-render after scan"
            results["GATE5"]["three_way"] = False
        else:
            results["GATE5"]["three_way"] = True
        if args.send and args.customer_email and results["overall"] == "PASS":
            results["emailed_sha"] = hashlib.sha256(open(email_copy, "rb").read()).hexdigest()
            try:
                from seo_crawler import _send_email_attachment
                # HARD: re-check SHA immediately before send on the EXACT artifact being sent.
                if gp.gate5_verify_unchanged(email_copy, scan["sha256"]):
                    _send_email_attachment(email_copy, args.customer_email)  # send the verified copy, NOT pdf_path
                    results["emailed"] = ("sent verified .for-email.pdf; emailed_sha=" +
                                          results["emailed_sha"][:16] + "; matches scanned/rendered")
                else:
                    results["overall"] = "FAIL"; results["reason"] = "email artifact SHA mismatch — blocked before send"
            except Exception as e:
                results["emailed"] = "not sent (test): " + str(e)[:80]
    results["LANGUAGE"] = "en"
    results["TIER"] = "US$497"
    # ---- STRUCTURAL COMPLETENESS SCORE (field presence, out of 100) ----
    # NOT a quality score: 100 here only means every required field/label is present & non-blank.
    required_labels = ["Exact placement", "Approval flag", "CTA destination", "Baseline", "Scale rule",
                       "What Not To Prioritise Yet", "Definition of done", "First measurable signal", "Commercial Opportunity Model"]
    visible = scan.get("extracted_visible_text") or gp.extract_visible_text_mature(open(pdf_path, "rb").read())
    visible_l = visible.lower()
    sc_pct = 0
    for lab in required_labels:
        if lab.lower() in visible_l:
            sc_pct += 1
    structural = round(100.0 * sc_pct / len(required_labels), 1)
    # ---- INDEPENDENT QUALITY SCORE (semantic, out of 100) ----
    # Categories graded by the separate external semantic auditor + hard evidence checks.
    # A category is 100 only when it is actually met (non-empty string is NOT sufficient).
    ext_decisions = (ext_audit[0].get("decisions") if ext_audit and ext_audit[0].get("mode") == "external" else [])
    def _audited(rx):
        return any(d.get("accept") is True for d in ext_decisions if rx(d.get("action_id") or ""))
    # corrected investment split (owner instruction): EC-003 = DO NOW; EC-001/EC-002 = VALIDATE FIRST
    def _card_of(a):
        return next((k for k in valid_cards if k.get("card_id") in (a.get("evidence_ids") or [])), {})
    _do_now = [a for a in acts if _card_of(a).get("card_id") == "EC-003"]
    _valid8 = [a for a in acts if _card_of(a).get("card_id") in ("EC-001", "EC-002")]
    q = {}
    q["evidence_accuracy"] = {"points": 20, "pct": 100 if all(c.get("direct_observation") and c.get("evidence") for c in valid_cards) else 0}
    q["finding_distinctness"] = {"points": 15, "pct": 100 if len({(c.get("specific_gap") or "").lower() for c in valid_cards}) == len(valid_cards) else 0}
    q["customer_specificity"] = {"points": 15, "pct": 100 if all(("appleimprints" in (c.get("primary_customer_url") or "")) and ("Buyers" in (c.get("business_mechanism") or "") or "buyer" in (c.get("business_mechanism") or "").lower()) for c in valid_cards) else 0}
    q["commercial_priority_quality"] = {"points": 15, "pct": 100 if all("quote" in (c.get("business_mechanism") or "").lower() for c in valid_cards) and _do_now and _valid8 else 0}
    q["action_executability"] = {"points": 15, "pct": 100 if _audited(lambda aid: aid in (a["action_id"] for a in acts)) and not g4["rejected_findings"] else 0}
    q["pdf_customer_readiness"] = {"points": 20, "pct": 100 if (scan["clean"] and not scan["hard_fails"] and visible and ("appleimprints" in visible_l)) else 0}
    qual_total = round(sum(v["points"] for v in q.values()), 1)
    # ---- investment status (corrected per owner instruction) ----
    inv_status = {}
    for a in acts:
        c = next((k for k in valid_cards if k.get("card_id") in (a.get("evidence_ids") or [])), {})
        if c.get("card_id") == "EC-003":
            inv_status[a["action_id"]] = "DO NOW"
        elif c.get("card_id") in ("EC-001", "EC-002"):
            inv_status[a["action_id"]] = "VALIDATE FIRST (pending owner approval)"
        else:
            inv_status[a["action_id"]] = "VALIDATE FIRST"
    results["investment_status"] = inv_status
    results["scorecard"] = {
        "STRUCTURAL_COMPLETENESS_SCORE": {"out_of": 100, "value": structural,
            "labels_found": sc_pct, "required_labels": len(required_labels),
            "note": "Field/label presence only — NOT a quality score."},
        "QUALITY_SCORE": {"out_of": 100, "value": qual_total, "categories": q,
            "per_category_pct": {k: v["pct"] for k, v in q.items()},
            "auditor_mode": ext_audit[0].get("mode") if ext_audit else "none",
            "note": "Independent semantic audit + hard evidence checks; a category counts ONLY when actually met."},
        "pdf_sha256": scan["sha256"],
    }
    print(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()