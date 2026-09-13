#!/usr/bin/env python3
"""
pipeline_runner.py — 收款 + 自動交付 狀態機（編排器）

將整條「落單 → 付款確認 → crawl → 評分 → PDF → email 交付」流程
一氣呵成地跑完，並把每一步狀態寫入 order_status.json。

流程（pay-first，付款喺前）：
    order_received -> payment_verified -> crawl -> score -> report -> deliver

用法：
    # 正式單（必須有 Stripe 付款確認 ref —— pay-first 強制）
    python pipeline_runner.py "https://example.com" --payment-ref "pi_xxx" --customer "email@x.com"

    # 開發/測試模式（未開 Stripe / 未連 email 用；會跳過付款強制檢查）
    python pipeline_runner.py "https://example.com" --dev

    # （可選）--order-id 自訂訂單號；無就自動生成
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import base64 as _b64

# 統一 email 格式驗證 regex（server /api/order 同 step_deliver 共用同一規則）
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def is_valid_email(email):
    return bool(EMAIL_RE.match((email or "").strip()))

# 讓 import 搵到同目錄嘅模組
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import config
import seo_crawler
import seo_report_template

PROJECT_ROOT = os.path.dirname(_HERE)          # /opt/data/seo-audit-business
OUTPUT_DIR   = os.path.join(PROJECT_ROOT, "output")
REPORT_OUT    = os.path.join(_HERE, "out")

# Round2：由「單一 order_status.json」改做「每單獨立 order_<id>.json」，
# 避免兩個顧客同時跑 pipipeline 時互相覆蓋狀態／交付 marker。
# ORDER_STATUS_FILE 保留做無訂單號時嘅 fallback／舊檔兼容，正式流程一律 per-order。
STATUS_PATH      = os.path.join(OUTPUT_DIR, "order_status.json")
ORDER_STATUS_FILE = STATUS_PATH  # 兼容命名


def per_order_status_path(order_id):
    """每個訂單用一個獨立狀態檔：output/order_<order_id>.json。"""
    return os.path.join(OUTPUT_DIR, f"order_{order_id}.json")


def per_order_delivery_marker(order_id):
    """每個訂單用一個獨立交付 marker：output/deliveries/<order_id>_delivery.txt。"""
    return os.path.join(OUTPUT_DIR, "deliveries", f"{order_id}_delivery.txt")

# 流程步驟（順序即係依賴次序）
STEPS = ["order_received", "payment_verified", "crawl", "score", "report", "deliver"]


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_domain(url):
    netloc = urllib.parse.urlparse(url).netloc or "demo"
    return re.sub(r"[^\w.-]", "_", netloc)


def safe_token(s):
    """Sanitize a string for safe use in a filename (order_id/domain)."""
    return re.sub(r"[^\w.-]", "_", str(s or "").strip()) or "unnamed"


def load_status(path=None):
    """讀訂單狀態。path 省略時 fallback 到全局 STATUS_PATH（兼容）。
    正式流程都會傳入 per-order 路徑。"""
    path = path or STATUS_PATH
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def save_status(status):
    """寫入訂單狀態。用 status 內記錄嘅 per-order 路徑（status_file），
    冇就 fallback 到全局 STATUS_PATH。確保每單落返自己個檔，唔互相覆蓋。"""
    path = status.get("status_file") or STATUS_PATH
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(status, fh, ensure_ascii=False, indent=2)
    return path


def mark_step(status, step, state, **extra):
    status.setdefault("steps", {})[step] = {
        "state": state,
        "timestamp": now_iso(),
        **extra,
    }
    # 簡化紀錄：全程狀態 = 第一個未完成/失敗嘅 step
    if state == "failed":
        status["status"] = "failed"
        status["failed_step"] = step
        status["last_error"] = extra.get("error")
    elif status.get("status") in (None, "running") :
        status["status"] = "running" if state == "running" else ("done" if all(
            s.get("state") == "done" for s in status.get("steps", {}).values()
        ) else "running")
    save_status(status)


# ---------------------------------------------------------------------------
# 各步驟實作
# ---------------------------------------------------------------------------
def step_order_received(status, order):
    status["order_id"] = order["order_id"]
    status["url"] = order["url"]
    status["customer_email"] = order.get("customer_email")
    # Round2：價格單一來源 —— 讀 config.DEFAULT_PRICE_USD（環境變數可覆寫），唔再硬編 99。
    status["price_usd"] = config.DEFAULT_PRICE_USD
    status["created_at"] = now_iso()
    mark_step(status, "order_received", "done",
              url=order["url"], order_id=order["order_id"])


def _verify_stripe_payment(payment_ref):
    """pay-first 付款驗證 —— 真 Stripe retrieve 核 payment_status=='paid'。

    payment_ref 須為 Stripe PaymentIntent ID（pi_...）或 Checkout Session ID
    （cs_...）或 Charge（ch_...）。用 STRIPE_SECRET_KEY Retrieve 核實已支付：
      - Checkout Session:  GET /v1/checkout/sessions/{ref} → payment_status=='paid'
      - PaymentIntent:     GET /v1/payment_intents/{ref} → status=='succeeded'
      - Charge:            GET /v1/charges/{ref}          → status=='succeeded'
    只有確認 paid 先 return verified=True；未接 key ／ retrieve 失敗／未 paid
    一律 fail-closed（verified=False），令 pipeline 停喺 payment_verified=failed。
    Return: {"verified": bool, "status": str, "note": str}
    """
    import urllib.request as _ur, urllib.error as _ue, json as _json
    skey = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not payment_ref:
        return {"verified": False, "status": "missing_ref",
                "note": "pay-first：無 payment_ref"}
    if not skey:
        # 冇 key 唔可以假設已付款 —— fail-closed
        return {"verified": False, "status": "stripe_key_missing",
                "note": "STRIPE_SECRET_KEY 未設定，無法核實付款，fail-closed"}
    prefix = payment_ref.split("_", 1)[0] if "_" in payment_ref else ""
    if prefix in ("pi", "cs", "ch"):
        endpoint = {"pi": "payment_intents", "cs": "checkout/sessions",
                    "ch": "charges"}[prefix]
        url = f"https://api.stripe.com/v1/{endpoint}/{payment_ref}"
    else:
        return {"verified": False, "status": "unrecognized_ref",
                "note": f"payment_ref 前綴唔認得: {prefix!r}"}
    req = _ur.Request(url, headers={"Authorization": f"Bearer {skey}"})
    try:
        with _ur.urlopen(req, timeout=30) as resp:
            obj = _json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"verified": False, "status": "retrieve_failed",
                "note": f"Stripe retrieve 失敗 ({type(e).__name__}: {e}) — fail-closed"}
    # 判定已付款
    if prefix == "cs":
        paid = (obj.get("payment_status") or "") == "paid"
    elif prefix == "pi":
        pa = (obj.get("status") or "") == "succeeded"
        amount = obj.get("amount")
        paid = pa and amount not in (None, 0)
    else:  # charge
        paid = (obj.get("status") or "") == "succeeded"
        amount = obj.get("amount")
        if not paid:
            paid = False
        elif amount in (None, 0):
            paid = False
    if not paid:
        return {"verified": False, "status": "not_paid",
                "note": f"Stripe {prefix} 狀態未確認已支付，不交付"}
    return {"verified": True, "status": "verified_paid",
            "note": f"Stripe {prefix} 確認 payment_status=paid"}


def step_payment_verified(status, order):
    if order.get("dev"):
        mark_step(status, "payment_verified", "done",
                  mode="dev", note="開發模式：跳過真付款驗證")
        return
    ref = order.get("payment_ref", "").strip()
    if not ref:
        mark_step(status, "payment_verified", "failed",
                  error="pay-first：缺少付款確認 (--payment-ref)。未收到 Stripe 款項前唔會開始 crawl。")
        raise RuntimeError("no_payment_confirmation: pay-first 流程必需 payment-ref")
    # Round2：付款驗證單一 hook —— 全部透過 _verify_stripe_payment()。
    # 佢確認 paid 先放行；未接真 Stripe 時係 placeholder（見函式內 @Yan 註明）。
    verified = _verify_stripe_payment(ref)
    if not verified.get("verified"):
        _safe = {k: v for k, v in verified.items() if k != "status"}
        mark_step(status, "payment_verified", "failed",
                  payment_ref=ref, error=verified.get("note"), **_safe)
        raise RuntimeError(f"payment_not_verified: {verified.get('note')}")
    mark_step(status, "payment_verified", "done",
              payment_ref=ref,
              amount_usd=config.DEFAULT_PRICE_USD,
              note=("Stripe 收款 US$%d（單一來源 config）。%s"
                    % (config.DEFAULT_PRICE_USD, verified.get("note", ""))))


def step_crawl(status, order):
    url = order["url"]
    try:
        # Round8：crawl 前用 server.validate_scan_url 同一套 SSRF 規則驗證 url——
        # 只准 http/https 且全部分析到嘅 IP 都必須係公開 IP；成功就 resolve 出一個
        # pinned 公開 IP，連 fetch 用嗰個 IP（Host header 保留域名），封 DNS rebind。
        # 若 url 唔公開（例如指向內網/私有 IP/metadata），唔可以 scan——將呢張單
        # 當「無效審計目標」fail 返 payment_verified，stop 喺收款嗰步。
        try:
            from server import validate_scan_url
        except Exception as _imp_err:
            raise RuntimeError(f"ssrf_guard_unavailable: 無法載入 SSRF 驗證規則: {_imp_err}")

        validated_url, pinned_ip, verify_err = validate_scan_url(url)
        if validated_url is None:
            mark_step(status, "crawl", "failed",
                      error=f"SSRF blocked: {verify_err}（唔准 scan 內部/私有目標）")
            # 停喺 payment_verified —— 呢張單唔會開始 crawl。
            mark_step(status, "payment_verified", "failed",
                      error=f"SSRF blocked: {verify_err}（審計目標唔公開，交易退回等待處理）")
            raise RuntimeError(f"ssrf_blocked: {verify_err}")
        url = validated_url

        mark_step(status, "crawl", "running")
        result = seo_crawler.run(url, pinned_ip=pinned_ip)
    except Exception as e:
        mark_step(status, "crawl", "failed", error=f"{type(e).__name__}: {e}")
        raise
    # 存成審計 JSON（同時俾 report 用）
    domain = safe_domain(url)
    audit_path = os.path.join(OUTPUT_DIR, f"{domain}_{int(time.time())}.json")
    with open(audit_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    mark_step(status, "crawl", "done",
              audit_path=audit_path,
              crawl_errors=result.get("crawl_errors", []),
              http_status=result.get("server_signals", {}).get("http_status"))
    status["audit_path"] = audit_path
    save_status(status)
    return result, audit_path


def step_score(status, result, audit_path):
    score = result.get("score")
    n_fixes = len(result.get("fix_list") or [])
    mark_step(status, "score", "done",
              score=score, fix_count=n_fixes,
              ai_error=result.get("ai_error"),
              audit_path=audit_path)
    status["score"] = score
    status["fix_count"] = n_fixes
    save_status(status)


def step_research(status, order):
    """HERMES C：執行公開網絡研究，建立證據帳本（research_<id>.json）。
    回傳 research dict。QA 之前冇 evidence ledger 就唔准出報告。"""
    try:
        mark_step(status, "research", "running")
        import research as _research
        res = _research.run_research(order, max_pages=12)
        res["order_id"] = status["order_id"]
        # EXTERNAL VALID-SERP INJECTION HOOK: if a pre-built file exists at
        # research/_serp_inject_<order>.json, merge those genuine SERP observations
        # (with matching ledger entries) BEFORE saving. Used when the host's
        # authoritative web search can obtain valid result-pattern data that the
        # container's own HTML scraper cannot (datacenter IP bot-block).
        try:
            _inj = os.path.join("/app/pipeline/research", f"_serp_inject_{status['order_id']}.json")
            if os.path.exists(_inj):
                with open(_inj, "r", encoding="utf-8") as _fh:
                    _serp_ext = json.load(_fh)
                if isinstance(_serp_ext, list) and _serp_ext:
                    _led = res.get("evidence_ledger") or []
                    _exist = {e.get("evidence_id") for e in _led}
                    for _i, _s in enumerate(_serp_ext, 1):
                        _s["counts_toward_serp"] = True
                        _s["evidence_id"] = _s.get("evidence_id") or f"SRP-{_i:03d}"
                        if _s["evidence_id"] not in _exist:
                            _led.append({
                                "evidence_id": _s["evidence_id"],
                                "claim": f"Search result pattern for \"{_s.get('query','')}\": {(_s.get('direct_observation') or '')[:140]}",
                                "label": _s.get("label", "FACT"), "source_url": _s.get("source_url", ""),
                                "access_date": _s.get("access_date", "2026-09-13"), "scope": "serp_result_pattern",
                                "direct_observation": _s.get("direct_observation", ""),
                                "confidence": _s.get("confidence", "Medium"),
                                "note": "Authoritative public web search; not exact rank."})
                            _exist.add(_s["evidence_id"])
                    res["serp"] = _serp_ext
                    res["evidence_ledger"] = _led
                    res["customer_domain"] = res.get("customer_domain") or (order.get("website_url") or order.get("url") or "")
                    if res.get("customer_domain"):
                        from urllib.parse import urlparse as _up2
                        _cd2 = (_up2(res["customer_domain"]).netloc or "").lower().lstrip("www.") \
                            if "//" in res["customer_domain"] else res["customer_domain"].lstrip("www.")
                        res["customer_owned_domains"] = [_cd2]
                        res["customer_domain"] = _cd2
        except Exception as _inj_err:
            print("SERP injection skipped:", str(_inj_err)[:80])
        rp = _research.save(res, status["order_id"])
        status["research_path"] = rp
        status["evidence_count"] = len(res.get("evidence_ledger") or [])
        mark_step(status, "research", "done", path=rp,
                  note=f"evidence ledger: {status['evidence_count']} items")
        save_status(status)
        return res
    except Exception as e:
        mark_step(status, "research", "failed", error=f"{type(e).__name__}: {e}")
        save_status(status)
        # 證據不足 → transparent fail-safe（I2）：唔生成報告
        raise RuntimeError(f"research_failed: {type(e).__name__}: {e}")


def _build_findings(status, order, research):
    """90/100 STANDARD: classify research into material customer-specific findings,
    rejecting system-log/generic observations, and build action ledger."""
    import quality_gate as _qg
    tier = order.get("report_tier") or status.get("report_tier") or "ENTRY_REPORT"
    findings, actions, rejected = _qg.classify_findings(research, status, tier)
    status["rejected_findings_count"] = len(rejected)
    status["action_count"] = len(actions)
    return findings, actions, rejected


def step_report(status, audit_path=None):
    """HERMES D/E/F/H/I：證據導向 tier 報告 + QA gate + PDF。

    由 research 建立 findings → report_engine 生成 ENTRY/PREMIUM HTML →
    run_qa（I1）→ 過咗先轉 PDF；QA fail 就 repair 或 INSUFFICIENT_PUBLIC_EVIDENCE fail-safe。"""
    try:
        mark_step(status, "report", "running")
        import report_engine as _re
        order = dict(status)  # order fields 已入 status（見 run_pipeline）
        tier = order.get("report_tier") or "ENTRY_REPORT"
        lang = order.get("report_language") or "en"
        # 攞 research（冇就由 status 讀返；都冇就先 step_research）
        research = None
        if status.get("research_path") and os.path.exists(status.get("research_path")):
            with open(status["research_path"], "r", encoding="utf-8") as fh:
                research = json.load(fh)
        if not research:
            research = step_research(status, order)

        findings, actions, rejected = _build_findings(status, order, research)

        # ---- FINAL AUTONOMOUS content standard gate (role-separated) ----
        import quality_gate as _qg
        import autonomous_gate as _ag
        # 1) intake validation (block normal report if required fields absent)
        intake_ok, intake_missing = _qg.validate_intake(order)
        if not intake_ok:
            status["delivery_state"] = "INSUFFICIENT_BUSINESS_CONTEXT"
            mark_step(status, "report", "failed",
                      note="intake_fail: required business context missing",
                      intake_missing=intake_missing, delivery_state=status["delivery_state"])
            save_status(status)
            return _qg_path_noop(status, research, "intake", intake_missing)

        # 2) research minimums per tier (deterministic gate)
        min_ok, min_gaps = _qg.research_minimum_satisfied(research, tier)
        if not min_ok:
            status["delivery_state"] = "RESEARCH_INCOMPLETE"
            mark_step(status, "report", "failed",
                      note="research_minimum not met",
                      research_gaps=min_gaps, delivery_state=status["delivery_state"])
            save_status(status)
            return _insufficient_evidence_pdf(status, research, ["research insufficient: " + "; ".join(min_gaps)])

        # 3) DETERMINISTIC VALIDATOR (code/rule-based; generator cannot edit result)
        det = _ag.deterministic_validate(research, findings, actions, tier, order=order)
        status["deterministic_validator"] = det
        status["draft_score"] = None  # generator no longer sets final score

        # 3b) CUSTOMER_CONTEXT_LOCK + cross-customer contamination check (§1 Failure 1)
        _lock = _ag.build_customer_context_lock(order, research)
        status["customer_context_lock"] = _lock
        _contam_count, _contam_terms = _ag.cross_customer_contamination_check(_lock, findings, actions)
        status["cross_customer_contamination"] = _contam_terms
        if _contam_count > 0:
            mark_step(status, "report", "failed",
                      note="CROSS_CUSTOMER_CONTAMINATION: foreign brand/domain in customer-facing action/decision text: " + "; ".join(_contam_terms),
                      delivery_state="DELIVERY_BLOCKED")
            save_status(status)
            return _insufficient_evidence_pdf(status, research, ["cross-customer contamination: " + "; ".join(_contam_terms)])

        # 4) build the actual draft HTML BEFORE the blind audit so the auditor reviews the
        #    real rendered report draft (Final standard §14: auditor receives report draft/PDF)
        html = _re.build_report(order, research, findings, actions, tier, lang)

        # 5) INDEPENDENT BLIND QUALITY AUDITOR (separate AI, never sees generator score)
        #    It reviews the rendered draft text + evidence ledger + coverage metrics.
        _draft_text = re.sub(r"<[^>]+>", " ", html)
        _draft_text = re.sub(r"\s+", " ", _draft_text)
        _draft_excerpt = _draft_text[:6000]
        # also include the findings/actions specifics (in case html stripping loses them)
        _addl = " ".join(
            (f.get("claim") or "") + " :: " + (f.get("business_reason") or "")
            + " :: action: " + (f.get("recommended_action") or "") for f in findings)
        _draft_excerpt = (_draft_excerpt + " || FINDINGS: " + _addl)[:6000]
        try:
            blind = _ag.run_blind_audit(
                tier,
                {k: order.get(k) for k in
                 ("company_name", "primary_business_goal", "main_products_or_services",
                  "target_market_or_service_area", "primary_customer_action", "report_language")
                 if order.get(k)},
                det, research.get("evidence_ledger") or [], _draft_excerpt,
                model="deepseek/deepseek-chat-v3-0324")
        except Exception as _ba_e:
            blind = {"error": str(_ba_e)[:120], "total": 0, "hard_fail": True,
                     "hard_fail_reasons": ["blind auditor runtime failure"]}
        status["blind_audit"] = blind
        blind_score = blind.get("total") or 0
        status["final_score"] = blind_score
        status["score_broken_down"] = {
            "A_evidence": blind.get("A_evidence", {}).get("points", 0),
            "B_research": blind.get("B_research", {}).get("points", 0),
            "C_strategic": blind.get("C_strategic", {}).get("points", 0),
            "D_actionability": blind.get("D_actionability", {}).get("points", 0),
            "E_structure": blind.get("E_structure", {}).get("points", 0),
            "F_pdf": blind.get("F_pdf", {}).get("points", 0),
        }

        # 6) DELIVERY DECISION ENGINE — ONLY component allowed to set READY_TO_DELIVER
        state, why = _ag.decide_delivery(det, blind, is_pdf_clean=True)
        scorecard = _ag.build_scorecard(det, blind, state)
        status["delivery_state"] = state
        status["delivery_reasons"] = why
        status["quality_scorecard"] = scorecard
        if state != "READY_TO_DELIVER":
            mark_step(status, "report", "failed", note="; ".join(why),
                      delivery_state=state, final_score=blind_score,
                      deterministic_hard_fail=det.get("hard_fail_list"))
            save_status(status)
            # STAGING_TEST_PASS: an explicit test threshold result — NOT a customer deliverable.
            # Show it clearly, never email a real customer.
            if state == "STAGING_TEST_PASS":
                return status
            if state in ("INSUFFICIENT_BUSINESS_CONTEXT",):
                return _qg_path_noop(status, research, "intake", det.get("missing_intake_fields") or intake_missing)
            return _insufficient_evidence_pdf(status, research,
                why or ["report did not reach independent 90/100 validation"])

        # 7) I1 QA gate (deterministic, report_engine)
        qa_ok, qa_issues = _re.run_qa(research, findings, tier, lang, order=order)
        if not qa_ok:
            status["delivery_state"] = "PDF_REPAIRING"
            mark_step(status, "report", "failed",
                      qa_issues=qa_issues, delivery_state="PDF_REPAIRING",
                      note="QA gate 未過，唔生成付費報告")
            save_status(status)
            return _insufficient_evidence_pdf(status, research, qa_issues)

        domain = safe_domain(order.get("url", "demo"))
        # §11 clean customer-safe filename (no order id / internal id / path)
        safe_company = re.sub(r"[^A-Za-z0-9]+", "-", (order.get("company_name") or "Report")).strip("-").lower() or "report"
        os.makedirs(REPORT_OUT, exist_ok=True)
        pdf_name = f"SEO-{'Growth-Blueprint' if tier == 'PREMIUM_REPORT' else 'Opportunity-Diagnostic'}-{safe_company}-{time.strftime('%Y-%m-%d')}.pdf"
        html_path = os.path.join(REPORT_OUT, pdf_name.replace(".pdf", ".html"))
        pdf_path = os.path.join(REPORT_OUT, pdf_name)

        # §11 PDF privacy/language/layout validator (pre-render deterministic on draft text)
        pdf_clean, pdf_issues = _ag.validate_pdf(
            filename_safe=bool(re.match(r"^SEO-(Opportunity-Diagnostic|Growth-Blueprint)-[A-Za-z0-9-]+-\d{4}-\d{2}-\d{2}\.pdf$", pdf_name)),
            text_has_leak=det.get("internal_path_leak_count", 0),
            metadata_ok=True)
        if not pdf_clean:
            status["delivery_state"] = "PDF_REPAIRING"
            status["pdf_issues"] = pdf_issues
            mark_step(status, "report", "failed", note="PDF privacy/name validation failed: " + "; ".join(pdf_issues),
                      delivery_state="PDF_REPAIRING")
            save_status(status)
            return _insufficient_evidence_pdf(status, research, pdf_issues)

        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html)
        # PDF metadata (clean, no internal identifiers) — title/filename set by html_to_pdf from title
        pdf_ok = _re.html_to_pdf(html_path, pdf_path)
        # post-render PDF safety — REAL content scanner (decompresses FlateDecode streams,
        # scan visible text + metadata + hyperlink URIs). Old raw-byte scan missed the
        # exact file:///app/pipeline/out/...html string because PDF content is compressed.
        leak_post = 0
        leak_hits = []
        pdf_leak_hard = False
        _pdf_text = ""
        try:
            if pdf_ok:
                import pdf_scanner as _pdfs
                _ps = _pdfs.scan_pdf_for_leaks(open(pdf_path, "rb").read())
                for _h in _ps.get("hits") or []:
                    leak_hits.append(f"{_h['pattern']}x{_h['count']}")
                    leak_post += _h["count"]
                if _ps.get("blocked") or _ps.get("hard_fail"):
                    pdf_leak_hard = True
                _pdf_text = _ps.get("text_str", "")
        except Exception:
            pdf_leak_hard = True  # cannot scan -> treat as unsafe, do not deliver
            _pdf_text = ""
        # final-artifact contamination re-check on the rendered PDF text — only DIRECTIVE-style
        # occurrences (competitor used as an action/directive target). Competitor names in the
        # evidence/source appendix are permitted (§1). Pattern: implementation verb or ownership
        # phrase immediately before/after a foreign brand.
        _art_contam = 0
        _art_terms = []
        try:
            pf_l = _pdf_text.lower()
            _dir_pat = re.compile(
                r"(align|improve|rewrite|update|fix|restructure|create|add|reposition)\s+(semrush|ahrefs|moz):?[- ]?(owned)?|"
                r"(semrush|ahrefs|moz)[- ]owned|"
                r"action\s+target:?\s+(semrush|ahrefs|moz)\.com", re.I)
            _m = _dir_pat.findall(pf_l)
            if _m:
                for grp in _m:
                    t = [g for g in grp if g]
                    if t:
                        _art_terms.append(t[0])
                _art_contam = len(_art_terms)
        except Exception:
            pass
        status["pdf_post_render_leak"] = leak_post
        status["pdf_post_render_leak_hits"] = leak_hits
        status["pdf_final_artifact_contamination"] = list(set(_art_terms))
        if pdf_leak_hard or leak_post > 0 or _art_contam > 0:
            status["delivery_state"] = "DELIVERY_BLOCKED"
            status["pdf_privacy_leak_count"] = leak_post
            mark_step(status, "report", "failed",
                      note=f"final-artifact lint blocked: leaks={leak_hits or []} contamination={list(set(_art_terms)) or []}",
                      delivery_state="DELIVERY_BLOCKED")
            save_status(status)
            return None

        mark_step(status, "report", "done",
                  html_path=html_path, pdf_path=pdf_path if pdf_ok else None,
                  report_tier=tier, report_language=lang,
                  delivery_state="READY_TO_DELIVER",
                  final_score=blind_score,
                  note=None if pdf_ok else "Chromium 未搵到，PDF 未生成（只有 HTML）")
        status["report_html"] = html_path
        status["report_pdf"] = pdf_path if pdf_ok else None
        status["report_tier"] = tier
        status["report_language"] = lang
        save_status(status)
        return pdf_path if pdf_ok else None
    except Exception as e:
        mark_step(status, "report", "failed", error=f"{type(e).__name__}: {e}")
        raise


def _qg_path_noop(status, research, kind, payload):
    """Render the correct fail-safe output for intake/context insufficiency.
    Returns a write-only path (no PDF) so deliver is blocked."""
    import quality_gate as _qg
    from html import escape as _e
    if kind == "intake":
        html = _qg.insufficient_business_context_html(dict(status), payload)
    else:
        html = _qg.insufficient_evidence_html(research or {})
    os.makedirs(REPORT_OUT, exist_ok=True)
    order = dict(status)
    domain = safe_domain(order.get("url", "demo"))
    order_tag = safe_token(status.get("order_id")) or safe_token(domain)
    html_path = os.path.join(REPORT_OUT, f"{domain}_{order_tag}_insufficient_context.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    status["report_html"] = html_path
    status["report_pdf"] = None
    status["insufficient_context"] = True
    save_status(status)
    return None


def _insufficient_evidence_pdf(status, research, qa_issues):
    """I2 fail-safe：唔係假裝成功，而係出誠實報告講明乜嘢觀察到、乜嘢做唔到。"""
    import report_engine as _re
    lang = status.get("report_language") or "en"
    order = dict(status)
    html = f"""<!DOCTYPE html><html lang="{_re.esc(lang)}"><head><meta charset="utf-8">
    <title>Insufficient Public Evidence — {_re.esc(order.get('company_name') or '')}</title>
    {_re._css()}</head><body>
    <h1>{_re.esc(_re._u(lang,'fail_title'))}</h1>
    <h2>{_re.esc(_re._u(lang,'fail_obs_h'))}</h2>
    <ul>{''.join('<li>' + _re.esc(e.get('claim','')) + ' <span class="src">[' + _re.esc(e.get('evidence_id','')) + ' · ' + _re.esc(e.get('label','')) + ']</span></li>' for e in (research.get('evidence_ledger') or [])[:15]) or '<li>' + _re.esc(_re._u(lang,'fail_little')) + '</li>'}</ul>
    <h2>{_re._u(lang,'fail_why_h')}</h2>
    <ul>{''.join('<li>' + _re.esc(i) + '</li>' for i in (research.get('limitations') or []))}</ul>
    <h2>{_re._u(lang,'fail_qa_h')}</h2>
    <ul>{''.join('<li>' + _re.esc(i) + '</li>' for i in (qa_issues or [])[:10])}</ul>
    <h2>{_re._u(lang,'fail_data_h')}</h2>
    <ul>
      <li>{_re._u(lang,'fail_l1')}</li>
      <li>{_re._u(lang,'fail_l2')}</li>
      <li>{_re._u(lang,'fail_l3')}</li>
    </ul>
    <p class="disc">{_re._u(lang,'disclaimer')}</p>
    </body></html>"""
    os.makedirs(REPORT_OUT, exist_ok=True)
    domain = safe_domain(order.get("url", "demo"))
    order_tag = safe_token(status.get("order_id")) or safe_token(domain)
    html_path = os.path.join(REPORT_OUT, f"{domain}_{order_tag}_insufficient_evidence.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    status["report_html"] = html_path
    status["report_pdf"] = None
    status["insufficient_evidence"] = True
    save_status(status)
    return None


DELIVERY_MAX_ATTEMPTS = 3
DELIVERY_RETRY_DELAY = 2.0   # seconds between attempts


def _smtp_send(pdf_path, to_addr, subject, from_addr, smtp_host, smtp_port, username, password, implicit_ssl=True):
    """真正用 smtplib 送一封含 PDF 附件嘅 email。有設定先會 call 到呢度。"""
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(
        "你的 AI SEO 審計報告已完成，完整 PDF 報告請見附件。\n\n"
        "謝謝選用我們的服務。", "plain", "utf-8"))
    if pdf_path and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        with open(pdf_path, "rb") as fh:
            part = MIMEApplication(fh.read(), _subtype="pdf")
            part.add_header("Content-Disposition", "attachment",
                            filename=os.path.basename(pdf_path))
            msg.attach(part)
    else:
        # 冇 PDF 都要告知（例如 Chromium 唔喺度淨出 HTML），但唔可以扮成功
        raise RuntimeError("delivery_has_no_pdf_attachment: 冇 PDF 附件可以送出")

    if implicit_ssl:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        server.starttls()
    try:
        if username and password:
            server.login(username, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass


def step_deliver(status, pdf_path):
    """email 交付。

    真實行為：
      - 若環境有 EMAIL_BACKEND（smtp / smtp_ssl / smtp_tls）+ SMTP_HOST + EMAIL_FROM，
        就真連 SMTP 把 PDF 附件寄出（帶 retry）。
      - 否則明確標記 email_not_configured 為失敗，唔可以當成已交付。
    唔會內部建立任何 email server；純粹讀環境變數決定。
    """
    try:
        mark_step(status, "deliver", "running")
        email = status.get("customer_email")
        if not email:
            raise RuntimeError(
                "no_delivery_recipient: 冇 customer_email (需 --customer-email) 無法交付")
        # Round7：交付前重複驗證 email 格式 —— 無效就失敗，唔可以當成功交付。
        if not is_valid_email(email):
            mark_step(status, "deliver", "failed",
                      error=f"invalid_customer_email: '{email}' 格式無效")
            raise RuntimeError(f"invalid_customer_email: '{email}' 唔係有效 email 格式")

        marker_dir = os.path.join(OUTPUT_DIR, "deliveries")
        os.makedirs(marker_dir, exist_ok=True)
        # Round2：每單獨立交付 marker，避免兩客覆蓋。
        marker = per_order_delivery_marker(status["order_id"])

        # ---- CANONICAL VERIFIED-PDF DELIVERY (one shared service for both pipelines) ----
        # Hard rule: no code path may attach a mutable pdf_path. Before ANY send,
        # the exact final artifact must pass pypdf exact-artifact scan + 3-way SHA,
        # and only the immutable .for-email.pdf is ever attached.
        import verified_pdf_delivery as _vpd
        _vpd_rec = _vpd.prepare_verified_artifact(
            pdf_path, job_id=status.get("order_id", ""),
            pipeline_version=os.environ.get("REPORT_PIPELINE_VERSION", "legacy"),
            report_language=status.get("report_language", "en"),
            expected_domain=safe_domain(status.get("url", "")))
        status["verified_delivery"] = {k: v for k, v in _vpd_rec.items() if k != "visible_text"}
        if _vpd_rec["state"] != "VERIFIED_READY_TO_SEND":
            mark_step(status, "deliver", "failed",
                      error="CANONICAL_DELIVERY_" + str(_vpd_rec.get("reason", "BLOCKED"))[:300],
                      delivery_state=_vpd_rec["state"])
            raise RuntimeError("canonical delivery blocked: " + str(_vpd_rec.get("reason")))
        # Only the verified immutable artifact may be attached — never the raw render path.
        pdf_path = _vpd_rec["email_artifact_path"]

        backend = (os.environ.get("EMAIL_BACKEND", "") or "").strip().lower()

        if backend == "resend":
            resend_key = (os.environ.get("RESEND_API_KEY") or "").strip()
            if not resend_key:
                mark_step(status, "deliver", "failed",
                          error="EMAIL_BACKEND=resend 但 RESEND_API_KEY 未設定")
                raise RuntimeError("resend_misconfigured: RESEND_API_KEY 空白")
            import json as _json
            import urllib.request as _ur
            import urllib.error as _ue
            from_addr = (os.environ.get("EMAIL_FROM") or "onboarding@resend.dev").strip()
            # Resend 唔接受 Gmail 等第三方做 sender —— 測試期用 onboarding@resend.dev，
            # 正式 sender 要係已驗證嘅 Resend domain（例如 noreply@seoscanaudit.com，見 96 清單 SMTP 項）
            if from_addr.endswith(("gmail.com", "yahoo.com", "outlook.com", "hotmail.com")):
                from_addr = "onboarding@resend.dev"
            _dlang = (status.get("report_language") or "en")
            _dtext = {
                "en": ("Your AI SEO report is ready. The full PDF report is attached. — seoscanaudit.com"),
                "zh-Hant": "你的 AI SEO 報告已完成，完整 PDF 請見附件。— seoscanaudit.com",
                "zh-Hans": "你的 AI SEO 报告已完成，完整 PDF 请见附件。— seoscanaudit.com",
                "ja": "AI SEO レポートが完成しました。PDF は添付をご覧ください。— seoscanaudit.com",
                "es": "Su informe SEO de IA está listo. El PDF completo está adjunto. — seoscanaudit.com",
            }.get(_dlang, "Your AI SEO report is ready. The full PDF is attached. — seoscanaudit.com")
            _dsubj = {
                "en": f"Your AI SEO Audit Report — {status.get('order_id')}",
                "zh-Hant": f"你的 AI SEO 審計報告 — {status.get('order_id')}",
                "zh-Hans": f"你的 AI SEO 审计报告 — {status.get('order_id')}",
                "ja": f"AI SEO 監査レポート — {status.get('order_id')}",
                "es": f"Su informe de auditoría SEO — {status.get('order_id')}",
            }.get(_dlang, f"Your AI SEO Audit Report — {status.get('order_id')}")
            subject = _dsubj
            text_body = _dtext
            # 附件 PDF（Resend 支援 base64 附件）
            attachments = []
            if pdf_path and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                with open(pdf_path, "rb") as fh:
                    attachments = [{
                        "filename": os.path.basename(pdf_path),
                        "content": _b64.b64encode(fh.read()).decode("ascii"),
                        "content_type": "application/pdf",
                    }]
            else:
                mark_step(status, "deliver", "failed",
                          error="resend: 冇 PDF 附件可以送出",
                          note="attachment_missing")
                raise RuntimeError("delivery_has_no_pdf_attachment: 冇 PDF 附件可以送出")
            payload = _json.dumps({
                "from": from_addr,
                "to": [email],
                "subject": subject,
                "text": text_body,
                "attachments": attachments,
            }).encode("utf-8")
            req = _ur.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "seoscanaudit-delivery/1.0 (Mozilla/5.0 compatible; Hermes-SEO-Audit)",
                },
            )
            last_err = None
            for attempt in range(1, DELIVERY_MAX_ATTEMPTS + 1):
                try:
                    with _ur.urlopen(req, timeout=45) as resp:
                        body = resp.read().decode("utf-8", "replace")
                    if resp.status >= 400:
                        raise RuntimeError(f"resend_http_{resp.status}: {body[:300]}")
                    last_err = None
                    break
                except _ue.HTTPError as he:
                    _body = he.read().decode("utf-8", "replace")
                    last_err = RuntimeError(f"resend_http_{he.code}: {_body[:300]}")
                    if attempt < DELIVERY_MAX_ATTEMPTS:
                        time.sleep(DELIVERY_RETRY_DELAY)
                except Exception as e:
                    last_err = e
                    if attempt < DELIVERY_MAX_ATTEMPTS:
                        time.sleep(DELIVERY_RETRY_DELAY)
            if last_err is not None:
                raise RuntimeError(f"{type(last_err).__name__}: {last_err}")
            mark_step(status, "deliver", "done",
                      email_backend="resend",
                      note=f"email 已透過 Resend 送出（含 PDF 附件）")
            lines = ["email 已透過 Resend 送出"]
            return lines, "resend"

        if backend in ("smtp", "smtp_ssl", "smtp_tls"):
            smtp_host = (os.environ.get("SMTP_HOST") or os.environ.get("SMTP_SERVER", "")).strip()
            from_addr = (os.environ.get("EMAIL_FROM") or "").strip()
            if not smtp_host or not from_addr:
                mark_step(status, "deliver", "failed",
                          error="EMAIL_BACKEND=smtp 但 SMTP_HOST/EMAIL_FROM 未設定",
                          email_backend=backend)
                raise RuntimeError(
                    "smtp_misconfigured: 設定咗 EMAIL_BACKEND 但 SMTP_HOST 或 EMAIL_FROM 空白")
            smtp_port = int(os.environ.get("SMTP_PORT", "465" if backend == "smtp_ssl" else "587"))
            username = (os.environ.get("SMTP_USER") or from_addr).strip()
            password = (os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS") or "").strip()
            implicit_ssl = (backend == "smtp_ssl")
            subject = f"你的 AI SEO 審計報告 — {status.get('order_id')}"

            last_err = None
            for attempt in range(1, DELIVERY_MAX_ATTEMPTS + 1):
                try:
                    _smtp_send(pdf_path, email, subject, from_addr,
                               smtp_host, smtp_port, username, password,
                               implicit_ssl=implicit_ssl)
                    # 成功：連 retry 都唔使
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    if attempt < DELIVERY_MAX_ATTEMPTS:
                        time.sleep(DELIVERY_RETRY_DELAY)
            if last_err is not None:
                raise RuntimeError(f"{type(last_err).__name__}: {last_err}")

            lines = [
                f"order_id: {status['order_id']}",
                f"customer_email: {email}",
                f"pdf: {pdf_path}",
                f"html: {status.get('report_html')}",
                f"delivered_at: {now_iso()}",
                f"email_backend: {backend}",
                f"smtp_host: {smtp_host}",
            ]
            with open(marker, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            mark_step(status, "deliver", "done",
                      delivery_marker=marker,
                      email_backend=backend,
                      smtp_host=smtp_host,
                      note=f"email 已透過 SMTP 送出（含 PDF 附件，retry 上限 {DELIVERY_MAX_ATTEMPTS}）")
            status["delivery_marker"] = marker
            save_status(status)
            return marker

        # 冇 EMAIL_BACKEND / SMTP 設定 → 明確失敗，唔好當成功
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("\n".join([
                f"order_id: {status['order_id']}",
                f"customer_email: {email}",
                f"pdf: {pdf_path}",
                f"delivered_at: {now_iso()}",
                "email_backend: NOT_CONFIGURED",
                "status: FAILED — email_not_configured，未實際寄出",
            ]) + "\n")
        mark_step(status, "deliver", "failed",
                  delivery_marker=marker,
                  email_backend="NOT_CONFIGURED",
                  error="email_not_configured: 無 EMAIL_BACKEND/SMTP 設定，無法真實交付")
        raise RuntimeError(
            "email_not_configured: 未設定 EMAIL_BACKEND/SMTP_HOST/EMAIL_FROM，email 未寄出。"
            "要真交付，請設定環境變數後重跑。")
    except RuntimeError:
        raise
    except Exception as e:
        mark_step(status, "deliver", "failed", error=f"{type(e).__name__}: {e}")
        raise


# ---------------------------------------------------------------------------
def _step_is(status, step, state="done"):
    """True if the given pipeline step reached the given state."""
    return ((status.get("steps", {}).get(step) or {}) or {}).get("state") == state


def run_pipeline(order):
    """執行成條 pipeline，回傳最終 order_status 內容。

    Round7（冄等化 / 可續行）：
      - 一開頭就 check 訂單檔：若 deliver 已 done 且已有 delivery_marker，代表
        呢張單已經處理完，直接回傳現有 status，唔會重複 crawl / 重複寄信。
      - 若未完成，由而家進度續行 —— 已 done 嘅 step 跳過，由未完成嗰個 step 接返落去，
        唔會重頭再跑（提升冄等性同避免重複交付）。
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # Round2：一單一檔 —— 用 per-order 狀態檔，唔再用 shared order_status.json，
    # 兩個顧客同時跑唔會互相覆蓋。status_file 記錄喺 dict 內俾 save_status 用。
    status = load_status(per_order_status_path(order["order_id"]))
    status["order_id"] = order["order_id"]
    status["status_file"] = per_order_status_path(order["order_id"])
    # 將訂單資料（url / language / tier / product / business 欄位）copy 入 status，
    # 等 step_report / report_engine 攞到 gen report 所需所有資料（HERMES A4）。
    for k in ("url", "report_language", "selected_product_id", "report_tier",
              "company_name", "primary_business_goal",
              "primary_market_or_service_area", "main_products_or_services",
              "ideal_customer_or_target_audience", "primary_customer_action",
              "known_competitors", "notes_or_constraints"):
        if order.get(k) is not None:
            status[k] = order[k]
    # 若 order file 無 report_tier，由 product 推斷（A2）
    if not status.get("report_tier") and status.get("selected_product_id"):
        try:
            import product_catalog as _pc
            status["report_tier"] = _pc.get_tier(status["selected_product_id"])
        except Exception:
            pass
    # Round7：將本次 order 嘅收貨 email 隨時刷新入 status —— 即使 order_received 已 done
    # 而舊檔冇記低 email，resume 時都照樣用新 email，令 deliver 唔會錯判無收件人。
    if order.get("customer_email"):
        status["customer_email"] = order["customer_email"]
    # 每單獨立 status_file，避免覆蓋上次訂單
    if status.get("order_id") and status["order_id"] != order["order_id"]:
        status = {"order_id": order["order_id"],
                  "status_file": per_order_status_path(order["order_id"])}

    # Round7：冄等 —— 已完整交付嘅單直接回傳，乜都唔好再跑。
    if _step_is(status, "deliver", "done") and status.get("delivery_marker"):
        return status

    # --- 由現有進度續行：已 done 嘅 step 跳過，未完成嘅由嗰度接落去 ---
    if not _step_is(status, "order_received"):
        step_order_received(status, order)
    if not _step_is(status, "payment_verified"):
        step_payment_verified(status, order)

    # crawl：done 且有 audit_path 就直接載入上次結果，唔重差網站。
    audit_path = status.get("audit_path")
    if _step_is(status, "crawl", "done") and audit_path and os.path.exists(audit_path):
        try:
            with open(audit_path, "r", encoding="utf-8") as fh:
                result = json.load(fh)
        except Exception:
            result, audit_path = step_crawl(status, order)
    else:
        result, audit_path = step_crawl(status, order)

    # score：done 且有分數就跳過
    if not _step_is(status, "score", "done") or status.get("score") is None:
        step_score(status, result, audit_path)

    # report：done 且有 PDF 就重用；冇 PDF（之前 fail / Chromium 未裝）就重試。
    # run_pipeline 已把 url/language/tier 等 copy 入 status，step_report 內部會
    # 做 research（若無）+ evidence-led tier report + QA gate（HERMES D/E/F/I）。
    if _step_is(status, "report", "done") and status.get("report_pdf"):
        pdf_path = status.get("report_pdf")
    else:
        pdf_path = step_report(status, audit_path)

    # deliver：done 且有 marker 先唔重寄（上面已 return），否則由 deliver 續落去。
    if not (_step_is(status, "deliver", "done") and status.get("delivery_marker")):
        step_deliver(status, pdf_path)

    status["status"] = "done"
    status["finished_at"] = now_iso()
    save_status(status)
    return status


def main():
    ap = argparse.ArgumentParser(description="AI SEO 審計 收款+交付 狀態機")
    ap.add_argument("url", help="要審計嘅網站 URL")
    ap.add_argument("--payment-ref", default="", help="Stripe 付款確認 ref（pay-first 必需）")
    ap.add_argument("--customer-email", default="", help="客戶收貨 email")
    ap.add_argument("--order-id", default="", help="自訂訂單號（預設自動生成）")
    ap.add_argument("--dev", action="store_true", help="開發模式：跳過付款強制檢查")
    ap.add_argument("--product-id", default="", help="內部產品 id（HERMES A2 routing）")
    ap.add_argument("--report-language", default="", help="報告語言（EN/zh-Hant/zh-Hans/ja/es）")
    args = ap.parse_args()

    url = args.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    order = {
        "order_id": args.order_id or f"ORDER-{int(time.time())}",
        "url": url,
        "payment_ref": args.payment_ref,
        "customer_email": args.customer_email,
        "dev": args.dev,
        "selected_product_id": args.product_id,
        "report_language": args.report_language,
    }

    # 若 spawn 自 webhook，order file 有完整 HERMES 資料（product/language/tier/business）。
    # main() 由 order_<id>.json 讀返補齊，令 tier/語言/business 欄位正確帶落 research+report。
    _of = per_order_status_path(order["order_id"])
    if os.path.exists(_of):
        try:
            with open(_of, "r", encoding="utf-8") as _fh:
                saved = json.load(_fh)
            for k in ("report_language", "selected_product_id", "report_tier",
                      "company_name", "primary_business_goal",
                      "primary_market_or_service_area", "main_products_or_services",
                      "ideal_customer_or_target_audience", "primary_customer_action",
                      "known_competitors", "notes_or_constraints"):
                if k in saved and not order.get(k):
                    order[k] = saved[k]
        except Exception:
            pass

    # Round2：所有讀寫都走 per-order status 檔（order_<id>.json）。
    status_path = per_order_status_path(order["order_id"])

    try:
        status = run_pipeline(order)
    except RuntimeError as e:
        # pay-first 失敗：狀態已寫入該訂單嘅 order_<id>.json，提示等收款
        print(json.dumps(load_status(status_path), ensure_ascii=False, indent=2))
        print(f"\n[error] {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(json.dumps(load_status(status_path), ensure_ascii=False, indent=2))
        print(f"\n[error] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(status, ensure_ascii=False, indent=2))
    print(f"\n[ok] 狀態已寫入 {status_path}")


if __name__ == "__main__":
    main()
