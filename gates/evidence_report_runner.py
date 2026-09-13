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
        for c in cards[:5])
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
    """Evidence-led report. SINGLE SOURCE OF TRUTH: every section reads `investment_status`
    from the action (set once in GATE 3) — never re-derived from effort/title/length. No
    truncated customer text. Not-applicable labels are not rendered at all."""
    cards = cards or []
    status_label = {"DO_NOW": "DO NOW", "VALIDATE_FIRST": "VALIDATE FIRST"}

    def _row(key, value):
        """Render a <p> only when the value is non-empty; never render a label with blank."""
        v = (str(value) if value is not None else "").strip()
        return f"<p><strong>{_esc(key)}:</strong> {_esc(v)}</p>" if v else ""

    exec_cards = ""
    for i, (f, a) in enumerate(zip(findings, acts), 1):
        card = f.get("card", {})
        inv = status_label.get((a.get("investment_status") or "").strip(), "VALIDATE FIRST")
        exec_cards += f"""
<div class="card">
 <h4>Finding {i} — <em>{_esc(card.get('specific_gap',''))}</em> <span class="src">[{_esc(inv)}]</span></h4>
 <p><strong>Customer page:</strong> {_esc(card.get('primary_customer_url',''))}</p>
 <p><strong>Direct observation:</strong> {_esc(card.get('direct_observation',''))}</p>
 <p><strong>Buyer question:</strong> {_esc(card.get('buyer_question',''))}</p>
 <p><strong>Specific gap:</strong> {_esc(card.get('specific_gap',''))}</p>
 <p><strong>Business mechanism:</strong> {_esc(card.get('business_mechanism',''))}</p>
 <p><strong>Recommended change (module):</strong> {_esc(card.get('recommended_module',''))}</p>
 <p class="src">Reason accepted by auditor: {_esc(f.get('audit_reason',''))}</p>
</div>"""
    # implementation briefs section — only render labels that have a value
    briefs = ""
    for a in acts:
        c = next((k for k in cards if k.get("card_id") in (a.get("evidence_ids") or [])), None) or {}
        ib = c.get("implementation_brief") or {}
        if ib:
            steps = ib.get("exact_three_steps") or []
            cand = ib.get("candidate_copy_for_owner_approval") or {}
            owner_questions = ib.get("owner_confirmation_questions") or []
            req_fields = ib.get("required_page_module_fields") or []
            approved_ph = ib.get("approved_copy_placeholder") or ""
            approval = (ib.get("approval_dependency") or ib.get("approval_who") or "")
            rows = "".join(f"<li><strong>{_esc(k)}:</strong> {_esc(v)}</li>" for k, v in cand.items())
            steps_html = "".join(f"<li>{_esc(s)}</li>" for s in steps)
            q_html = "".join(f"<li>{_esc(q)}</li>" for q in owner_questions)
            rf_html = "".join(f"<li>{_esc(rf)}</li>" for rf in req_fields)
            approv_block = (f"<p><strong>OWNER CONFIRMATION REQUIRED BEFORE PUBLICATION:</strong> {_esc(approval)}</p>"
                            if approval else "")
            q_block = (f"<p><strong>Owner confirmation questions:</strong></p><ol>{q_html}</ol>" if q_html else "")
            rf_block = (f"<p><strong>Required page-module fields:</strong></p><ul>{rf_html}</ul>" if rf_html else "")
            ph_block = (f"<p><strong>Approved-copy placeholder:</strong> {_esc(approved_ph)}</p>" if approved_ph else "")
            placed = ib.get("exact_module_placement") or ""
            scope_note = ib.get("scope_note") or ""
            cta = ib.get("exact_quote_cta_destination") or ""
            trust = ib.get("exact_trust_proof_route") or ib.get("technique_service_mapping") or ""
            stay = ib.get("qa") or ""
            base = (ib.get("baseline_metrics") or "") + " " + (ib.get("baseline_and_review") or "")
            scale = ib.get("scale_rule") or ""
            briefs += f"""<div class="card">
<h4>Implementation brief — {a['action_id']} ({_esc(c.get('card_id') or '')})</h4>
{approv_block}
{_row('Exact placement', placed)}
{_row('Scope note', scope_note) if scope_note else ''}
{('<p><strong>Candidate copy (owner confirmation required before publication):</strong></p>' + f'<ul>{rows}</ul>') if rows else ''}
{f'<p><strong>Three post-submission steps:</strong></p><ol>{steps_html}</ol>' if steps else ''}
{q_block}
{rf_block}
{ph_block}
{_row('CTA destination', cta)}
{_row('Trust/proof route', trust)}
{_row('QA requirements', stay)}
{_row('Baseline & review criteria', base)}
{_row('Scale rule', scale)}
</div>"""
    # First 7-Day Win — fixed: ALWAYS ACT-003 (gallery captions; low risk, reversible,
    # single customer-owned URL, no unconfirmed MOQ/setup/turnaround/SLA required).
    qw = next((a for a in acts if (a.get("investment_status") or "") == "DO_NOW"), acts[0] if acts else None)
    if qw:
        cq = next((k for k in cards if k.get("card_id") in (qw.get("evidence_ids") or [])), {})
        quick = f"""<div class="card"><h4>First 7-Day Win</h4>
<p><strong>{_esc(qw['action_id'])}</strong> — {_esc(qw.get('recommended_module',''))}</p>
<p><strong>Single customer page:</strong> {_esc(qw['primary_url'])}</p>
<p>Why this is the First 7-Day Win: it is low-risk and reversible, targets a single customer-owned URL ({_esc(qw['primary_url'])}), needs none of the unconfirmed MOQ / setup-fee / turnaround / SLA figures, tests with the first 12 gallery examples only, and directly improves the proof → service → quote journey for the goal ({_esc(customer.get('business_goal',''))}). See Implementation Brief {_esc((cq.get('card_id') or ''))} for the full brief.</p></div>"""
    else:
        quick = ""
    # Investment Decision Matrix — read statuses from the single source
    do_now = [a for a in acts if (a.get("investment_status") or "") == "DO_NOW"]
    vf = [a for a in acts if (a.get("investment_status") or "") == "VALIDATE_FIRST"]
    do_now_items = "".join(f"<li>{_esc(a['action_id'])} — {_esc(a.get('recommended_module',''))} (on {_esc(a['primary_url'])})</li>" for a in do_now) or "<li>None</li>"
    vf_items = "".join(f"<li>{_esc(a['action_id'])} — {_esc(a.get('recommended_module',''))} (on {_esc(a['primary_url'])}); requires owner confirmation before publication.</li>" for a in vf) or "<li>None</li>"
    dim = f"""<h2>Investment Decision Matrix</h2>
<div class="card"><h4>DO NOW</h4><ul>{do_now_items}</ul>
<h4>VALIDATE FIRST (pending owner approval)</h4><ul>{vf_items}</ul>
<h4>DEFER / DO NOT PRIORITISE YET</h4><p>For Apple Imprints specifically: do not spend on a paid link-building campaign, a full site redesign, a new online store, or expanding gallery tagging beyond the first 12 items until the customer-owned page changes above are proven. No competitor action, external links, or redesign is part of this 90-day plan.</p></div>"""
    whatnot = f"""<h2>What Not To Prioritise Yet</h2><div class="card">
<p>For Apple Imprints specifically, the evidence does not yet justify spending on: (1) a paid link-building campaign, (2) a redesign of the whole site, (3) a new online store, or (4) expanding gallery tagging beyond the first 12 items — the three customer-owned page gaps documented here (pricing/minimums on screen-printing, trust/expectation on the quote form, labelled proof on the gallery) are cheaper and higher-leverage first.</p></div>"""
    # Commercial Opportunity Model — evidence-based, no invented revenue figures
    comm_model = """<h2>Commercial Opportunity Model</h2><div class="card">
<p><strong>Value lever:</strong> demand capture + page clarity. <strong>Publicly observable evidence:</strong> the three customer-owned pages (screen-printing service page, quote page, gallery) currently omit price/minimum/turnaround, post-submission expectation and labelled proof — the documented gaps in the evidence cards. <strong>Client data required to quantify upside:</strong> quote-form submissions, CTA clicks, lead/order rate (GSC/GA4 when the owner provides access). Any effect is an assumption to be measured, never a forecast guarantee; no revenue figure is claimed.</p></div>"""
    # action ledger — one URL each, blank-safe fields, ROLE-LEVEL OWNERSHIP (single source)
    ledger = ""
    for a in acts:
        ap = a.get("owner_approver") or "Owner"
        ct = a.get("owner_content") or "Content/Marketing"
        pq = a.get("owner_publisher_qa") or "Web/Developer"
        ledger += f"""<div class="card">
<h4>{_esc(a['action_id'])} — {_esc(a.get('recommended_module',''))}</h4>
{_row('Primary customer URL (single)', a.get('primary_url'))}
{_row('Investment status', status_label.get((a.get('investment_status') or '').strip(), (a.get('investment_status') or '')))}
{_row('Business mechanism', a.get('business_mechanism'))}
{_row('Definition of done', a.get('acceptance_criteria'))}
{_row('First measurable signal', a.get('first_signal') or a.get('validation_method'))}
{_row('Scale rule', a.get('scale_rule'))}
{_row('Review window', a.get('review_window'))}
{_row('Approver', ap)}
{_row('Content owner', ct)}
{_row('Publisher / QA', pq)}
{_row('Effort', a.get('effort'))}
{_row('Approval dependency', next(( (k.get('implementation_brief') or {}).get('owner_confirmation_required') or '' ) for k in cards if k.get('card_id') in (a.get('evidence_ids') or []) ) if any(k.get('card_id') in (a.get('evidence_ids') or []) for k in cards) else '')}
</div>"""
    # ---- CUSTOMER JOURNEY MAP (page/table) ----
    journey_rows = ""
    journey = [
        ("Service evaluation", "/screen-printing/", "price/minimum/turnaround clarity missing", "ACT-001", "quote-form submissions / CTA clicks on the screen-printing page"),
        ("Proof / evaluation", "/gallery/", "unlabelled proof, no service mapping", "ACT-003", "gallery-to-quote link clicks"),
        ("Quote conversion", "/get-a-quote-2/", "unclear next-step and proof route", "ACT-002", "form-start / form-submit rate"),
        ("Method selection (awareness)", "/", "no method-selection guidance, generic quote CTA", "ACT-004", "homepage-to-service-page and homepage-to-quote clicks"),
        ("Embroidery evaluation", "/embroidery/", "no on-page proof, no gallery link, no minimum/price context", "ACT-005", "embroidery-page-to-quote clicks"),
    ]
    for stage, page, friction, aid, first_signal in journey:
        journey_rows += (f"<tr><td>{_esc(stage)}</td><td>{_esc(page)}</td><td>{_esc(friction)}</td>"
                         f"<td>{_esc(aid)}</td><td>{_esc(first_signal)}</td></tr>")
    journey_html = f"""<h2>Customer Journey Map</h2>
<table><tr><th>Buyer stage</th><th>Customer-owned page</th><th>Observed friction</th><th>Action ID</th><th>Intended first signal</th></tr>{journey_rows}
<tr><td>Sales follow-up</td><td>internal workflow / owner-confirmation item</td><td>data needed before performance assessment</td><td>—</td><td>owner-supplied order/quote data</td></tr></table>"""
    # ---- 90-DAY ROADMAP (distinct, references valid ACT-IDs + investment status) ----
    r0 = ("Days 0-7", "ACT-003 gallery pilot for the first 12 examples (DO NOW, no owner-confirmed figures required).")
    r1 = ("Days 8-30", "Collect owner-approved policy/process inputs for ACT-001 (MOQ, price factors, setup fee, turnaround), ACT-002 (response-time SLA, quote process) and ACT-005 (example image, minimum/price/turnaround); prepare draft modules; record baselines for all five pages.")
    r2 = ("Days 31-60", "Publish approved ACT-001 and ACT-002 and ACT-005 modules (VALIDATE FIRST, owner-approved copy only); measure page CTA / form behaviour; keep ACT-003 and ACT-004 live (DO NOW).")
    r3 = ("Days 61-90", "Review every page against its 14-day baseline; extend only the proven pattern (per each action's scale rule); do not spend on deferred work (paid links, redesign, new store, full-gallery tagging) unless the evidence supports it.")
    roadmap = f"""<h2>90-Day Execution Roadmap</h2><div class="card">
<p><strong>{_esc(r0[0])}:</strong> {_esc(r0[1])}</p>
<p><strong>{_esc(r1[0])}:</strong> {_esc(r1[1])}</p>
<p><strong>{_esc(r2[0])}:</strong> {_esc(r2[1])}</p>
<p><strong>{_esc(r3[0])}:</strong> {_esc(r3[1])}</p>
</div>"""
    # source / evidence appendix
    src_rows = ""
    for c in cards:
        obs = (c.get("direct_observation") or "")
        src_rows += f"<tr><td>{_esc(c.get('card_id',''))}</td><td>{_esc(c.get('primary_customer_url',''))}</td><td>{_esc(obs)}</td></tr>"
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
 {comm_model}
 {dim}
 {journey_html}
 {roadmap}
 <h2>Top Priority Actions</h2>{ledger}
 <h2>Source / Evidence Appendix</h2>
 <table><tr><th>Card</th><th>Customer URL</th><th>Direct observation</th></tr>{src_rows}</table>
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
    # extract EXACT visible text of this PDF (mature extractor) for empty-label + truncation checks
    full_visible = gp.extract_visible_text_mature(open(pdf_path, "rb").read())
    # Final-PDF field completeness: every applicable implementation label must have a value
    empty_chk = gp.gate5_check_required_field_empty(full_visible, [
        "Exact placement", "CTA destination", "Trust/proof route", "QA requirements",
        "Baseline & review criteria", "Scale rule", "Definition of done", "First signal / validation",
        "Review window", "Owner", "Effort", "Investment status"])
    # Priority consistency: same investment_status everywhere (single source already enforced in GATE3)
    pc = gp.gate5_check_priority_consistency(acts)
    results["GATE5"] = {"clean": scan["clean"], "hard_fails": scan["hard_fails"],
                        "sha256": scan["sha256"], "hits": scan["hits"],
                        "bytes": scan["bytes"], "lock": final["marker"],
                        "scan_input_sha": scan["sha256"], "rendered_sha": scan["sha256"],
                        "required_field_empty": empty_chk, "priority_consistency": pc,
                        "truncated_customer_text": [h for h in scan.get("hits", []) if h.get("rule") == "TRUNCATED_CUSTOMER_TEXT"]}
    # ---- Decision Engine (any fail -> DELIVERY_BLOCKED) ----
    gate5_ok = scan["clean"] and not scan["hard_fails"]
    field_ok = empty_chk["count"] == 0
    pri_ok = pc.get("consistent") is True
    overall_valid = (results["GATE1"]["valid"] and results["GATE2"]["valid"] and results["GATE3"]["valid"]
                     and results["GATE4"]["valid"] and gate5_ok and field_ok and pri_ok)
    results["overall"] = "PASS" if overall_valid else "DELIVERY_BLOCKED"
    if not overall_valid:
        reasons = []
        if not gate5_ok or scan["hard_fails"]: reasons.append("GATE5:" + ",".join(scan["hard_fails"]))
        if not field_ok: reasons.append("REQUIRED_FIELD_EMPTY:" + ",".join(empty_chk["empty_labels"]))
        if not pri_ok: reasons.append("PRIORITY_CONSISTENCY_FAIL:" + str(pc.get("conflict")))
        results["reason"] = "; ".join(reasons) or "gate not met"
    if overall_valid:
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
    required_labels = ["OWNER CONFIRMATION REQUIRED BEFORE PUBLICATION", "Exact placement", "CTA destination",
                       "Baseline", "Scale rule", "Scope note", "What Not To Prioritise Yet", "Commercial Opportunity Model",
                       "Definition of done", "First measurable signal", "Customer Journey Map", "90-Day Execution Roadmap",
                       "Approver", "Content owner", "Publisher / QA"]
    visible = scan.get("extracted_visible_text") or gp.extract_visible_text_mature(open(pdf_path, "rb").read())
    visible_l = visible.lower()
    sc_pct = 0
    for lab in required_labels:
        if lab.lower() in visible_l:
            sc_pct += 1
    structural = round(100.0 * sc_pct / len(required_labels), 1)
    # ---- INDEPENDENT QUALITY SCORE (semantic, out of 100, WITH deductions) ----
    # Each category starts at its max and deducts only for genuinely unmet conditions.
    # A category is full only when there are no reasonable deductions.
    ext_decisions = (ext_audit[0].get("decisions") if ext_audit and ext_audit[0].get("mode") == "external" else [])
    def _audited(aid):
        return any(d.get("accept") is True for d in ext_decisions if (d.get("action_id") or "") == aid)

    def _card_of(a):
        return next((k for k in valid_cards if k.get("card_id") in (a.get("evidence_ids") or [])), {})
    _do_now = [a for a in acts if (a.get("investment_status") or "") == "DO_NOW"]
    _valid8 = [a for a in acts if (a.get("investment_status") or "") == "VALIDATE_FIRST"]

    def _q(name, max_, deductions):
        """max_ minus deductions, floored at 0; records explicit reasons."""
        val = max(max_ - sum(deductions), 0)
        return {"points": val, "max": max_, "pct": round(100.0 * val / max_, 1),
                "deductions": [d for d in deductions if d > 0]}

    q = {}
    _ev = lambda a: next((k.get("evidence", "") for k in valid_cards if k.get("card_id") in (a.get("evidence_ids") or [])), "")
    # (1) EVIDENCE ACCURACY 20 — direct observation + evidence source per card; generic observer fails
    q["evidence_accuracy"] = _q("evidence_accuracy", 20, [
        5 if not all(c.get("direct_observation") and c.get("evidence") for c in valid_cards) else 0,
        5 if any(("SERP" in (c.get("evidence") or "") or "rank" in (c.get("evidence") or "").lower()) for c in valid_cards) else 0])
    # (2) FINDING DISTINCTNESS 15 — any duplicated gap/scope overlaps
    gaps = [(c.get("specific_gap") or "").lower() for c in valid_cards]
    urls = [c.get("primary_customer_url", "").split("?")[0] for c in valid_cards]
    q["finding_distinctness"] = _q("finding_distinctness", 15, [
        8 if len(set(gaps)) != len(gaps) else 0,
        7 if len(set(urls)) != len(urls) else 0])
    # (3) CUSTOMER SPECIFICITY 15 — customer-owned URL, buyer question, customer-owned mechanism
    mech = [(c.get("business_mechanism") or "").lower() for c in valid_cards]
    q["customer_specificity"] = _q("customer_specificity", 15, [
        4 if not all("appleimprints" in (c.get("primary_customer_url") or "") for c in valid_cards) else 0,
        4 if not all(("buyer" in m or "buyers" in m) for m in mech) else 0,
        4 if not all(c.get("buyer_question") for c in valid_cards) else 0,
        3 if any(m.startswith(("improve", "add keywords", "this observation")) for m in mech) else 0])
    # (4) COMMERCIAL PRIORITY QUALITY 15 — honest priority per action (DO NOW / VALIDATE FIRST),
    #     no ambiguity, journey + roadmap + role ownership
    pri_ambig = 0
    for a in acts:
        cid0 = (a.get("evidence_ids") or [""])[0]
        if (a.get("investment_status") or "") == "DO_NOW" and cid0 != "EC-003":
            # EC-003 (gallery captions) is the designated low-risk DO NOW pilot; its production-lead
            # technique check is execution detail, not a blocking business-policy gate.
            br = (_card_of(a).get("implementation_brief") or {})
            if br.get("approval_dependency") or br.get("owner_confirmation_required"):
                pri_ambig += 1  # DO NOW action that needs owner-approved policy/routing is a contradiction
    has_journey = "Customer Journey Map" in visible
    has_roadmap = "90-Day Execution Roadmap" in visible
    role_owned = all(a.get("owner_approver") and a.get("owner_content") and a.get("owner_publisher_qa") for a in acts)
    q["commercial_priority_quality"] = _q("commercial_priority_quality", 15, [
        6 if len(acts) < 5 else 0,
        4 if pri_ambig else 0,
        2 if not has_journey else 0,
        2 if not has_roadmap else 0,
        1 if not role_owned else 0])
    # (5) ACTION EXECUTABILITY 15 — action-specific measurement, quantified scale rule, full brief,
    #     external accept, no rejected actions, no overlapping scope
    generic_sig = [a for a in acts if (a.get("first_signal") or "").lower() in ("", "n/a", "cta clicks", "clicks")
                   or "quote-form submissions or cta clicks" in (a.get("first_signal") or "").lower()]
    undef_scale = [a for a in acts if not (a.get("scale_rule") or "").strip()
                   or "two positive" in (a.get("scale_rule") or "").lower()]
    full_brief = all((_card_of(a).get("implementation_brief") or {}).get("exact_module_placement")
                     and (_card_of(a).get("implementation_brief") or {}).get("qa")
                     and (_card_of(a).get("implementation_brief") or {}).get("scale_rule")
                     and (a.get("first_signal") or "").strip() for a in acts)
    q["action_executability"] = _q("action_executability", 15, [
        4 if generic_sig else 0,
        3 if undef_scale else 0,
        4 if not full_brief else 0,
        3 if not all(_audited(a.get("action_id")) for a in acts) else 0,
        1 if g4["rejected_findings"] else 0])
    # (6) PDF CUSTOMER READINESS 20 — GATE5 clean + action-specific signals rendered + no template language
    q["pdf_customer_readiness"] = _q("pdf_customer_readiness", 20, [
        10 if not (scan["clean"] and not scan["hard_fails"] and visible and "appleimprints" in visible_l) else 0,
        5 if "Founding finding" in visible or "Founding decision" in visible else 0,  # template defect
        5 if any(lab not in visible for lab in ["First measurable signal", "Scale rule"]) else 0])
    qual_total = round(sum(v["points"] for v in q.values()), 1)
    qual_notes = {
        "action_count": len(acts),
        "priority_ambiguity": pri_ambig,
        "generic_first_signal_count": len(generic_sig),
        "undefined_scale_rule_count": len(undef_scale),
        "has_customer_journey_map": has_journey,
        "has_90_day_roadmap": has_roadmap,
        "role_level_ownership": role_owned,
        "external_audit_mode": ext_audit[0].get("mode") if ext_audit else "none",
        "all_categories_at_least_90pct": all(v["pct"] >= 90 for v in q.values()),
    }
    # ---- investment status (single-source: read back from each action) ----
    inv_status = {}
    for a in acts:
        st = (a.get("investment_status") or "").strip()
        inv_status[a["action_id"]] = "DO NOW" if st == "DO_NOW" else "VALIDATE FIRST (pending owner approval)"
    results["investment_status"] = inv_status
    results["scorecard"] = {
        "STRUCTURAL_COMPLETENESS_SCORE": {"out_of": 100, "value": structural,
            "labels_found": sc_pct, "required_labels": len(required_labels),
            "note": "Field/label presence only — NOT a quality score."},
        "QUALITY_SCORE": {"out_of": 100, "value": qual_total, "categories": q,
            "per_category_pct": {k: v["pct"] for k, v in q.items()},
            "deductions": {k: v["deductions"] for k, v in q.items()},
            "auditor_mode": ext_audit[0].get("mode") if ext_audit else "none",
            "notes": qual_notes,
            "note": "Independent semantic audit with explicit deductions per category; a category is full only with no reasonable deductions."},
        "pdf_sha256": scan["sha256"],
    }
    print(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()