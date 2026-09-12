import json, os, sys, time
HERE="/opt/data/seo-audit-business/pipeline"
sys.path.insert(0, HERE)
import pipeline_runner as pr
import seo_crawler, server, seo_report_template
import config as _cfg

results=[]
def chk(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), name, detail)

# --- Task6: email validation (both modules share same logic) ---
chk("email valid", server.is_valid_email("a.b+c@example.com"))
chk("email invalid 1", not server.is_valid_email("plainaddress"))
chk("email invalid 2", not server.is_valid_email("a@b"))
chk("email invalid 3", not server.is_valid_email("a@b."))
chk("email empty", not server.is_valid_email(""))
chk("pipe email reuses", pr.is_valid_email("x@y.io") and not pr.is_valid_email("nope"))

# --- Task4: SSRF guard blocks private/local (pure fn, no external net) ---
for bad in ["http://127.0.0.1", "http://localhost", "http://0.0.0.0", "ftp://x.com"]:
    url, pin, err = server.validate_scan_url(bad)
    chk("SSRF block "+bad, url is None, "err="+str(err))
url, pin, err = server.validate_scan_url("example.com")
chk("valid scan returns pinned", url is not None and pin and err is None, "pin="+str(pin)+" err="+str(err))

# --- Task5: idempotence — already-delivered order must early-return (no crawl/network) ---
os.makedirs(pr.OUTPUT_DIR, exist_ok=True)
oid="TEST-IDEM-"+str(int(time.time()))
sp=pr.per_order_status_path(oid)
complete={"order_id":oid,"status_file":sp,"status":"done","customer_email":"ok@x.com",
  "url":"https://example.com","score":77,"audit_path":"/nonexistent",
  "report_pdf":"/tmp/x.pdf","delivery_marker":"already-delivered-marker",
  "steps":{s:{"state":"done"} for s in pr.STEPS}}
with open(sp,"w") as f: json.dump(complete,f)
before=set(f for f in os.listdir(pr.OUTPUT_DIR) if f.endswith(".json"))
ret=pr.run_pipeline({"order_id":oid,"url":"https://example.com","payment_ref":"pi_x","customer_email":"ok@x.com"})
after=set(f for f in os.listdir(pr.OUTPUT_DIR) if f.endswith(".json"))
chk("idempotence: no new crawl files", before==after, "added="+str(after-before))
chk("idempotence: returns existing delivery_marker", ret.get("delivery_marker")=="already-delivered-marker")
chk("idempotence: status still done", ret.get("status")=="done")
os.remove(sp)

# --- Task6: step_deliver rejects invalid email (no SMTP call) ---
oid2="TEST-EMAIL-"+str(int(time.time()))
sp2=pr.per_order_status_path(oid2)
audit="/opt/data/seo-audit-business/output/hermes-agent.nousresearch.com_1789157634.json"
complete2={"order_id":oid2,"status_file":sp2,"status":"running","customer_email":"bad-email",
  "url":"https://example.com","score":60,"audit_path":audit,
  "report_pdf":"/tmp/fake.pdf",
  "steps":{s:{"state":"done"} for s in pr.STEPS if s!="deliver"}}
with open(sp2,"w") as f: json.dump(complete2,f)
try:
    pr.run_pipeline({"order_id":oid2,"url":"https://example.com","payment_ref":"pi_x","customer_email":"bad-email"})
    chk("deliver rejects invalid email", False, "should have raised")
except RuntimeError as e:
    chk("deliver rejects invalid email", "invalid_customer_email" in str(e), str(e)[:80])
with open(sp2,"r") as f: st=json.load(f)
chk("deliver step marked failed", st.get("steps",{}).get("deliver",{}).get("state")=="failed")
os.remove(sp2)

# --- Task5: resume — complete crawl+score+report but not deliver => no re-crawl, reaches deliver ---
oid3="TEST-RESUME-"+str(int(time.time()))
sp3=pr.per_order_status_path(oid3)
audit3="/opt/data/seo-audit-business/output/hermes-agent.nousresearch.com_1789157634.json"
data3=json.load(open(audit3))
complete3={"order_id":oid3,"status_file":sp3,"status":"running",
  "url":data3["url"],"score":data3.get("score"),"audit_path":audit3,
  "report_pdf":"/tmp/fake.pdf",
  "steps":{"order_received":{"state":"done"},"payment_verified":{"state":"done"},
           "crawl":{"state":"done"},"score":{"state":"done"},
           "report":{"state":"done","note":"fake"}}}
with open(sp3,"w") as f: json.dump(complete3,f)
try:
    pr.run_pipeline({"order_id":oid3,"url":data3["url"],"payment_ref":"pi_x","customer_email":"x@y.io"})
    chk("resume should hit deliver", False)
except RuntimeError as e:
    chk("resume reaches deliver (email_not_configured, no network)", "email_not_configured" in str(e), str(e)[:60])
with open(sp3,"r") as f: st=json.load(f)
chk("resume: report step not re-run", st.get("steps",{}).get("report",{}).get("state")=="done")
os.remove(sp3)

# --- Task7: report template renders data-quality badge ---
data=json.load(open(audit))
html=seo_report_template.build_html(data)
chk("report includes data-quality section", "數據品質 Data Quality" in html)
fb=dict(data); fb.setdefault("data_quality",{})["fallback_used"]=True
fb["data_quality"]["score_is_estimate"]=True
html_fb=seo_report_template.build_html(fb)
chk("fallback marks 規則估算非精確", "規則估算非精確" in html_fb and "品質徽章" in html_fb)
chk("fetch_ok badge present", "抓取成功 (fetch_ok)" in html)

# --- Round9: /api/scan 免費 tier 唔准洩漏 full fix_list ---
sample = {"url":"https://example.com","score":71,"fix_count":12,
          "fix_list":[{"priority":"high","issue":"x"}]*12,
          "top_issues":[{"priority":"high","issue":"x"}]*5,
          "version":"real-backend-v1"}
payload = server.shape_scan_response(sample)
chk("scan payload 冇 fix_list", "fix_list" not in payload, "keys="+str(sorted(payload)))
chk("scan payload 有 score", payload.get("score")==71)
chk("scan payload 有 fix_count", payload.get("fix_count")==12)
chk("scan payload 有 top_issues", len(payload.get("top_issues") or [])==5)
# checkout 鎖價：client 傳任意 price_usd 都要被 server 蓋返做 config 值
chk("checkout price 鎖 config.DEFAULT_PRICE_USD", server.checkout_price()==_cfg.DEFAULT_PRICE_USD)

failed=[r for r in results if not r[1]]
print("\nTOTAL", len(results), "FAILED", len(failed))
for f in failed: print("  FAILED:", f)
sys.exit(1 if failed else 0)