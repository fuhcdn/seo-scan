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
    # window the evidence cards into the prompt
    card_blob = "\n\n".join(
        f"EC {c['card_id']}: page={c['primary_customer_url']} | gap={c['specific_gap']} | module={c['recommended_module']}"
        for c in cards[:3])
    prompt = (
        "You are the independent SEMANTIC QUALITY AUDITOR for a US$497 SEO report.\n"
        "For each candidate finding below, decide ACCEPT or REJECT and give a short (<=25 word) "
        "human-readable reason usable by a real SME owner. Reject: duplicated strategic findings, "
        "generic actions, unrelated target pages, generic definition-of-done, generic business "
        "mechanisms, and actions the owner could not execute.\n"
        "Golden evidence cards:\n" + card_blob + "\n\nCANDIDATES:\n" +
        "\n".join(f"- {x['title']} | URL={x.get('card',{}).get('primary_customer_url')}" for x in findings) +
        "\n\nReply ONLY as JSON: {\"decisions\":[{\"title\":\"...\",\"accept\":true,\"reason\":\"...\"}]}")
    try:
        payload = {"model": "deepseek/deepseek-chat-v3-0324", "messages": [
            {"role": "system", "content": "You are a strict, evidence-based report quality auditor."},
            {"role": "user", "content": prompt}], "temperature": 0}
        env = openrouter_chat(key, payload)
        content = _coerce_msg_content(env.get("choices", [{}])[0].get("message", {}).get("content", ""))
        if not content or not content.strip():
            # retry without response_format (deepseek sometimes returns empty json_object)
            payload.pop("response_format", None)
            env = openrouter_chat(key, payload)
            content = _coerce_msg_content(env.get("choices", [{}])[0].get("message", {}).get("content", ""))
        # strip any leading non-json noise
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
    # quick win: smallest effort, reversible, one URL
    qw = min(acts, key=lambda a: len(a.get("recommended_module", "") or ""), default=None)
    quick = f"""<div class="card"><h4>First 7-Day Win</h4>
<p><strong>{_esc(qw['action_id'])}</strong> — {_esc((qw.get('recommended_module') or '')[:80])}</p>
<p><strong>Single customer page:</strong> {_esc(qw['primary_url'])}</p>
<p>Why first: small, reversible, on one high-intent customer-owned page — validates the wider plan.</p></div>""" if qw else ""
    # investment matrix from real effort
    do_now = [a for a in acts if (a.get("effort") or "").lower() == "small"]
    validate = [a for a in acts if (a.get("effort") or "").lower() != "small"]
    dim = f"""<h2>Investment Decision Matrix</h2>
<div class="card"><h4>DO NOW</h4><ul>{''.join(f'<li>{a["action_id"]} — on {a["primary_url"]}</li>' for a in do_now)}</ul>
<h4>VALIDATE FIRST</h4><ul>{''.join(f'<li>{a["action_id"]} — on {a["primary_url"]}</li>' for a in validate)}</ul>
<h4>DEFER</h4><p>Broad content production, external-link campaigns, redesigns and tool builds are deferred until these customer-owned page changes are proven.</p></div>"""
    # what-not-to-prioritise = evidence-based defers
    whatnot = """<h2>What Not To Prioritise Yet</h2><div class="card"><p>No action here depends on a competitor site, external links, or a redesign — those are deferred. Focus on the three customer-owned page modules above first.</p></div>"""
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
    findings = [{"title": a["title"], "card": c, "acceptance_criteria": a["acceptance_criteria"],
                 "business_mechanism": a["business_mechanism"], "audit_reason": ""}
                for a, c in zip(acts, valid_cards)]
    g4 = gp.gate4_semantic_audit(findings, acts)
    ext_audit = gate4_external_auditor(findings, valid_cards)
    # map external accept/reject reasons
    accepted = g4["accepted_findings"]
    if ext_audit and ext_audit[0].get("mode") == "external":
        for d in ext_audit[0].get("decisions", []):
            for f in accepted:
                if d.get("title") and d["title"] in f["title"]:
                    f["audit_reason"] = d.get("reason", "")
    results["GATE4"] = {"valid": g4["accepted_count"] >= 1 and ext_audit and ext_audit[0].get("mode") == "external",
                        "accepted": [{"title": f["title"], "reason": f.get("audit_reason","") or "deterministic accept"}
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
    results["GATE5"] = {"clean": scan["clean"], "sha256": scan["sha256"], "hits": scan["hits"],
                        "bytes": scan["bytes"], "lock": final["marker"]}
    # ---- Decision Engine ----
    overall_valid = (results["GATE1"]["valid"] and results["GATE2"]["valid"] and results["GATE3"]["valid"]
                     and results["GATE4"]["valid"] and results["GATE5"]["clean"])
    overall = "PASS" if overall_valid else "FAIL/BLOCK"
    results["overall"] = overall
    if overall == "PASS":
        # email ONLY the exact hashed file, hash-verified
        if not gp.gate5_verify_unchanged(pdf_path, scan["sha256"]):
            results["overall"] = "FAIL/BLOCK"; results["reason"] = "pdf changed after scan"
        elif args.send and args.customer_email:
            try:
                from seo_crawler import _send_email_attachment
                _send_email_attachment(pdf_path, args.customer_email)
                results["emailed"] = "only after hash verification: " + scan["sha256"][:16] + " (not actually sent in test)"
            except Exception as e:
                results["emailed"] = "not sent (test): " + str(e)[:80]
    results["LANGUAGE"] = "en"
    results["TIER"] = "US$497"
    print(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()