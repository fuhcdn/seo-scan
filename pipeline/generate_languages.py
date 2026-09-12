#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate 5-language landing pages for seoscanaudit.com
from a single shared skeleton (CSS/JS/logic identical) + per-language copy.

Outputs (in pipeline/):
  landing_page.html         English MASTER (served at /)
  landing_en.html           English  (served at /en)
  landing_zh-Hant.html      Trad. Chinese (served at /zh-Hant)
  landing_zh-Hans.html      Simp. Chinese (served at /zh-Hans)
  landing_ja.html           Japanese (served at /ja)
  landing_es.html           Spanish  (served at /es)

Pricing kept EXACT: Free US$0 / Full US$497 strike -> US$397 early-bird / Growth US$997.
7-day refund guarantee, authority badges, real /api/scan + /api/order + /api/create-checkout wiring all preserved.
No fake testimonials, no fake numbers.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Shared HTML skeleton. Every user-visible string is a {{TOKEN}}.
# Structure/CSS/JS/backend wiring is identical across all languages.
# ---------------------------------------------------------------------------
SKELETON = """<!DOCTYPE html>
<html lang="{{HTML_LANG}}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{{TITLE}}</title>
<meta name="description" content="{{META_DESC}}" />
<link rel="canonical" href="{{BASE_URL}}/{{URL_PATH}}" />
<link rel="alternate" hreflang="en" href="{{BASE_URL}}/" />
<link rel="alternate" hreflang="zh-Hant" href="{{BASE_URL}}/zh-Hant" />
<link rel="alternate" hreflang="zh-Hans" href="{{BASE_URL}}/zh-Hans" />
<link rel="alternate" hreflang="ja" href="{{BASE_URL}}/ja" />
<link rel="alternate" hreflang="es" href="{{BASE_URL}}/es" />
<link rel="alternate" hreflang="x-default" href="{{BASE_URL}}/" />
<style>
  :root{
    --ink:#0f172a; --muted:#64748b; --brand:#2563eb; --brand-dark:#1d4ed8;
    --bg:#f8fafc; --card:#ffffff; --line:#e2e8f0; --green:#16a34a;
    --amber:#d97706; --red:#dc2626; --shadow:0 10px 30px -12px rgba(15,23,42,.18);
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang HK","Microsoft JhengHei","Microsoft YaHei","Hiragino Sans","Noto Sans SC","Noto Sans JP","Noto Sans",sans-serif;
    color:var(--ink);background:var(--bg);line-height:1.6;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1080px;margin:0 auto;padding:0 24px}
  header{background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 60%,#3b82f6 100%);color:#fff;padding:64px 0 56px}
  .nav{display:flex;justify-content:space-between;align-items:center;padding:18px 0;font-size:14px;gap:12px;flex-wrap:wrap}
  .logo{font-weight:800;letter-spacing:.3px}
  .logo span{color:#bfdbfe}
  .nav-links{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
  .nav-links a{color:#334155;text-decoration:none;font-weight:600}
  .langbox select{appearance:none;background:#fff;border:1px solid var(--line);border-radius:999px;
    padding:7px 30px 7px 14px;font-size:13px;color:var(--ink);cursor:pointer;font-weight:600;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path d='M0 0l5 6 5-6z' fill='%2364748b'/></svg>");
    background-repeat:no-repeat;background-position:right 12px center;outline:none}
  .hero{text-align:center;padding:24px 0 8px}
  .badge{display:inline-block;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);
    padding:5px 14px;border-radius:999px;font-size:13px;margin-bottom:22px}
  h1{font-size:clamp(30px,5vw,46px);line-height:1.15;font-weight:800;margin-bottom:18px;letter-spacing:-.5px}
  h1 em{font-style:normal;color:#fbbf24}
  .sub{font-size:clamp(15px,2vw,18px);opacity:.92;max-width:640px;margin:0 auto}
  .scanbox{background:#fff;max-width:620px;margin:34px auto 0;padding:10px;border-radius:16px;
    box-shadow:var(--shadow);display:flex;gap:8px}
  .scanbox input{flex:1;border:none;outline:none;padding:14px 16px;font-size:16px;color:var(--ink);
    border-radius:10px;background:#f1f5f9;min-width:0}
  .scanbox input::placeholder{color:#94a3b8}
  .scanbox button{border:none;cursor:pointer;background:var(--brand);color:#fff;font-weight:700;
    padding:14px 22px;border-radius:10px;font-size:15px;white-space:nowrap;transition:background .2s}
  .scanbox button:hover{background:var(--brand-dark)}
  .ta{font-size:13px;color:#bfdbfe;margin-top:14px}
  .quick{color:#bfdbfe;font-size:13px;margin-top:6px}
  .quick b{color:#fff;cursor:pointer;text-decoration:underline}
  .stats{display:flex;gap:24px;justify-content:center;margin-top:36px;flex-wrap:wrap}
  .stats div{text-align:center;min-width:110px}
  .stats .n{font-size:24px;font-weight:800;color:#fbbf24}
  .stats .l{font-size:12px;opacity:.85}
  section{padding:64px 0}
  .h2{font-size:clamp(22px,3vw,30px);font-weight:800;text-align:center;margin-bottom:10px;letter-spacing:-.3px}
  .h2sub{text-align:center;color:var(--muted);max-width:520px;margin:0 auto 40px}
  .trustbar{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin:10px 0 18px}
  .trustbar span{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.28);
    color:#e2e8f0;padding:5px 12px;border-radius:99px;font-size:12px}
  .cv{display:grid;grid-template-columns:1fr 1.2fr;gap:20px;max-width:860px;margin:0 auto}
  .card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:28px;box-shadow:0 4px 14px rgba(15,23,42,.05)}
  .card .tag{font-size:12px;font-weight:700;letter-spacing:.5px;color:var(--muted);text-transform:uppercase}
  .card h3{font-size:22px;font-weight:800;margin:6px 0 4px}
  .card .price{font-size:34px;font-weight:800}
  .card .price small{font-size:14px;color:var(--muted);font-weight:500}
  .card ul{list-style:none;margin-top:18px}
  .card li{padding:7px 0 7px 28px;position:relative;font-size:15px}
  .card li:before{content:"✓";position:absolute;left:0;color:var(--green);font-weight:800}
  .card .lock li{color:#94a3b8}
  .card .lock li:before{content:"🔒";font-size:12px;left:2px;color:var(--amber)}
  .pro{position:relative;border:2px solid var(--brand);box-shadow:var(--shadow)}
  .ribbon{position:absolute;top:-14px;right:20px;background:var(--brand);color:#fff;font-size:12px;
    font-weight:700;padding:5px 14px;border-radius:999px}
  .cta-btn{display:block;text-align:center;background:var(--brand);color:#fff;border:none;cursor:pointer;
    font-weight:800;padding:16px;border-radius:12px;font-size:17px;margin-top:24px;width:100%;transition:background .2s}
  .cta-btn:hover{background:var(--brand-dark)}
  .cta-btn.ghost{background:#fff;color:var(--ink);border:1px solid var(--line)}
  .cta-btn.ghost:hover{background:#f1f5f9}
  .promo{background:#fffbeb;border:1px solid #fde68a;color:#92400e;text-align:center;font-size:14px;
    padding:10px 16px;border-radius:12px;margin-top:18px}
  .promo b{color:#b45309}
  .feats{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px;max-width:920px;margin:0 auto}
  .feat{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px}
  .feat .ico{font-size:26px;margin-bottom:10px}
  .feat h4{font-size:16px;font-weight:700;margin-bottom:6px}
  .feat p{font-size:14px;color:var(--muted)}
  footer{background:#0f172a;color:#94a3b8;padding:34px 0;text-align:center;font-size:13px}
  footer a{color:#cbd5e1;text-decoration:underline}
  .result{display:none;max-width:620px;margin:22px auto 0;background:#fff;border:1px solid var(--line);
    border-radius:16px;padding:24px;box-shadow:var(--shadow);text-align:left}
  .result h3{font-size:18px;margin-bottom:12px}
  .demoNote{display:none;background:#fffbeb;border:1px solid #fde68a;color:#92400e;font-size:12px;
    padding:8px 12px;border-radius:10px;margin-bottom:14px;line-height:1.5}
  .score{display:flex;align-items:center;gap:18px;margin-bottom:6px}
  .ring{width:74px;height:74px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    font-weight:800;font-size:22px;color:#fff;background:conic-gradient(var(--brand) 62%,#e2e8f0 0)}
  .ring span{background:#fff;border-radius:50%;width:58px;height:58px;display:flex;align-items:center;justify-content:center;color:var(--ink)}
  .toplist{margin-top:16px}
  .toplist .row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--line);font-size:14px}
  .toplist .lv{font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px}
  .lv.hi{background:#fee2e2;color:var(--red)}
  .lv.md{background:#fef3c7;color:var(--amber)}
  .lockrow{display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px dashed var(--line);
    color:#94a3b8;font-size:14px;cursor:pointer}
  .unlock{background:var(--brand);color:#fff;border:none;cursor:pointer;font-weight:800;padding:18px;
    border-radius:12px;font-size:17px;width:100%;margin-top:18px}
  .money{font-variant-numeric:tabular-nums}
  @media(max-width:700px){.scanbox{flex-direction:column}.scanbox button{width:100%}.cv{grid-template-columns:1fr}.ribbon{right:14px}}
</style>
</head>
<body id="top">

<!-- NAV -->
<nav class="wrap nav">
  <div class="logo">SEO<span>Scan</span>.ai</div>
  <div class="nav-links">
    <a href="#how">{{NAV_HOW}}</a>
    <a href="#pricing">{{NAV_PRICE}}</a>
    <span class="langbox">
      <select id="langSel" onchange="if(this.value){location.href=this.value}">
        <option value="/en" {{SEL_EN}}>English</option>
        <option value="/zh-Hant" {{SEL_ZHH}}>繁體中文</option>
        <option value="/zh-Hans" {{SEL_ZHS}}>简体中文</option>
        <option value="/ja" {{SEL_JA}}>日本語</option>
        <option value="/es" {{SEL_ES}}>Español</option>
      </select>
    </span>
  </div>
</nav>

<!-- HERO + FREE SCAN ENTRY -->
<header>
  <div class="wrap hero">
    <span class="badge">{{BADGE}}</span>
    <div class="trustbar">
      <span>✅ {{TB1}}</span>
      <span>✅ {{TB2}}</span>
      <span>✅ {{TB3}}</span>
    </div>
    <h1>{{H1_L1}}<br /><em>{{H1_EM}}</em>{{H1_L3}}</h1>
    <p class="sub">{{SUB}}</p>

    <div class="scanbox">
      <input id="url" type="url" placeholder="{{INPUT_PLACEHOLDER}}" required />
      <button onclick="runScan()">{{SCAN_BTN}}</button>
    </div>

    <div class="result" id="result">
      <h3>{{RESULT_TITLE}} <span id="rurl" style="color:var(--brand)"></span></h3>
      <div class="demoNote" id="demoNote" style="display:none"></div>
      <div class="score">
        <div class="ring"><span id="rscore">—</span></div>
        <div style="font-size:13px;color:var(--muted);line-height:1.5">
          {{SCORE_LABEL}}<br /><b style="font-size:22px;color:var(--ink);display:block"><span id="rscoreBig">—</span> / 100</b>
          <span id="rscoreHint" style="color:var(--amber)">{{SCORE_HINT}}</span>
        </div>
      </div>
      <div class="toplist">
        <div class="row"><span class="lv md">{{TOP_LV}}</span>{{TOP_PLACEHOLDER}}</div>
      </div>
      <div id="locked" style="margin-top:8px">
        <div class="lockrow"><span>🔒 {{LOCK_FIXLIST}}</span><b>{{LOCKED}}</b></div>
        <div class="lockrow"><span>🔒 {{LOCK_COMPETE}}</span><b>{{LOCKED}}</b></div>
        <div class="lockrow"><span>🔒 {{LOCK_AI_STEPS}}</span><b>{{LOCKED}}</b></div>
        <div style="margin:14px 0 4px;font-size:13px;color:var(--muted)">{{EMAIL_NOTE}}</div>
        <input id="email" type="email" placeholder="you@example.com" required
               style="width:100%;padding:12px 14px;font-size:15px;border:1px solid var(--line);border-radius:10px;outline:none;margin-bottom:10px" />
        <label style="display:flex;gap:8px;align-items:center;font-size:12px;color:var(--muted);margin-bottom:12px">
          <input id="consent" type="checkbox" required style="width:16px;height:16px;accent-color:var(--brand)" />
          {{CONSENT}}
        </label>
        <button class="unlock" onclick="startCheckout()">{{UNLOCK_BTN}}</button>
        <div style="margin:10px 0 2px;font-size:12px;color:#16a34a;font-weight:600">{{GUARANTEE}}</div>
        <div style="font-size:11px;color:var(--muted)">{{AUTO_DELIVER}}</div>
      </div>
    </div>

    <div class="ta">{{TA}}</div>
    <div class="quick">{{QUICK}}
      <b onclick="document.getElementById('url').value='restaurant-hk.com'">restaurant-hk.com</b></div>

    <div class="stats">
      <div><div class="n" id="scanCount">{{STAT1_N}}</div><div class="l">{{STAT1_L}}</div></div>
      <div><div class="n">{{STAT2_N}}</div><div class="l">{{STAT2_L}}</div></div>
      <div><div class="n">{{STAT3_N}}</div><div class="l">{{STAT3_L}}</div></div>
    </div>
  </div>
</header>

<!-- HOW -->
<section id="how">
  <div class="wrap">
    <div class="h2">{{HOW_H2}}</div>
    <p class="h2sub">{{HOW_SUB}}</p>
    <div class="feats">
      <div class="feat"><div class="ico">1️⃣</div><h4>{{F1_T}}</h4><p>{{F1_D}}</p></div>
      <div class="feat"><div class="ico">2️⃣</div><h4>{{F2_T}}</h4><p>{{F2_D}}</p></div>
      <div class="feat"><div class="ico">3️⃣</div><h4>{{F3_T}}</h4><p>{{F3_D}}</p></div>
    </div>
  </div>
</section>

<!-- PRICING -->
<section id="pricing" style="background:#fff">
  <div class="wrap">
    <div class="h2">{{PRICE_H2}}</div>
    <p class="h2sub">{{PRICE_SUB}}</p>
    <div class="cv" style="gap:18px;align-items:stretch">
      <div class="card">
        <div class="tag">{{FREE_TAG}}</div>
        <h3>Free Scan</h3>
        <div class="price money">US$0</div>
        <ul>
          <li>{{FREE_1}}</li>
          <li>{{FREE_2}}</li>
          <li>{{FREE_3}}</li>
          <li>{{FREE_4}}</li>
        </ul>
        <a class="cta-btn ghost" href="#how" style="text-decoration:none">↑ {{FREE_CTA}}</a>
      </div>
      <div class="card pro" style="border:2px solid var(--brand);position:relative">
        <div class="tag" style="background:var(--brand);color:#fff">{{PRO_TAG}}</div>
        <h3>Full AI SEO Audit</h3>
        <div class="price money"><del style="font-size:16px;color:var(--muted);margin-right:8px">US$497</del> <span style="color:var(--brand)">US$397</span> <small>{{PRO_UNIT}}</small></div>
        <div class="promo" style="font-size:12px;color:var(--muted);margin:2px 0 12px">{{PRO_PROMO}}</div>
        <ul class="lock">
          <li>{{PRO_1}}</li>
          <li>{{PRO_2}}</li>
          <li>{{PRO_3}}</li>
          <li>{{PRO_4}}</li>
          <li>{{PRO_5}}</li>
          <li>{{PRO_6}}</li>
        </ul>
        <button class="cta-btn" onclick="document.getElementById('url').scrollIntoView({behavior:'smooth'});document.getElementById('url').focus()">{{PRO_CTA}}</button>
      </div>
      <div class="card">
        <div class="tag">{{GROWTH_TAG}}</div>
        <h3>Growth Audit</h3>
        <div class="price money">US$997 <small>{{GROWTH_UNIT}}</small></div>
        <ul class="lock">
          <li>{{GROWTH_1}}</li>
          <li>{{GROWTH_2}}</li>
          <li>{{GROWTH_3}}</li>
          <li>{{GROWTH_4}}</li>
          <li>{{GROWTH_5}}</li>
          <li>{{GROWTH_6}}</li>
        </ul>
        <button class="cta-btn ghost" onclick="document.getElementById('url').scrollIntoView({behavior:'smooth'});document.getElementById('url').focus()">{{GROWTH_CTA}}</button>
      </div>
    </div>
  </div>
</section>

<!-- SOCIAL PROOF -->
<section>
  <div class="wrap">
    <div class="h2">{{PROOF_H2}}</div>
    <p class="h2sub">{{PROOF_SUB}}</p>
  </div>
</section>

<!-- URGENCY -->
<section style="padding:44px 0">
  <div class="wrap" style="max-width:640px;text-align:center">
    <div style="font-size:40px;margin-bottom:8px">⏳</div>
    <div class="h2" style="font-size:26px;margin-bottom:6px">{{URG_H2}}</div>
    <p style="color:var(--muted);margin-bottom:22px">{{URG_P}}</p>
    <a class="scanbox" href="#top" style="text-decoration:none;cursor:pointer;justify-content:center;background:var(--brand);color:#fff;font-weight:800" onclick="document.getElementById('url').focus()">
      {{URG_CTA}} →
    </a>
  </div>
</section>

<footer>
  <div class="wrap">
    {{FOOT1}}<br />
    <a href="/legal/privacy">{{FOOT_PRIVACY}}</a> · <a href="/legal/terms">{{FOOT_TERMS}}</a> · <a href="/legal/refund">{{FOOT_REFUND}}</a> · <a href="/legal/disclaimer">{{FOOT_DISCLAIMER}}</a><br />
    {{COPYRIGHT}}
  </div>
</footer>

<script>
  var DEMO_MODE = false;

  function runScan(){
    var u = document.getElementById('url').value.trim();
    if(!u){ document.getElementById('url').focus(); return; }

    document.getElementById('rscore').textContent = '…';
    document.getElementById('demoNote').style.display = 'none';
    document.getElementById('result').style.display = 'block';
    document.getElementById('result').scrollIntoView({behavior:'smooth', block:'center'});

    fetch('/api/scan', {method:'POST', headers:{'Content-Type':'application/json'},
           body: JSON.stringify({url: u})})
      .then(function(r){ return r.json(); })
      .then(function(data){
        if (data.error){
          document.getElementById('rscore').textContent = '—';
          document.getElementById('demoNote').style.display = 'block';
          document.getElementById('demoNote').textContent = '{{SCAN_ERR}}' + data.error;
          return;
        }
        var clean = u.replace(/^https?:\\/\\//,'').replace(/\\/$/,'');
        var scVal = (data.score != null) ? data.score : '—';
        document.getElementById('rscore').textContent = scVal;
        var big = document.getElementById('rscoreBig');
        if(big) big.textContent = scVal;
        var hint = document.getElementById('rscoreHint');
        if(hint) hint.textContent = (data.score != null) ? ((data.score >= 80 ? '{{HINT_GOOD}}' : (data.score >= 50 ? '{{HINT_MID}}' : '{{HINT_BAD}}'))) : '{{HINT_NODIAG}}';
        document.getElementById('rurl').textContent = clean;

        var fc = (data.fix_count != null) ? data.fix_count : (data.fix_list || []).length;
        document.querySelectorAll('.fixCount').forEach(function(el){ el.textContent = fc; });

        var top = (data.top_issues || []).slice(0,5);
        var list = document.getElementById('toplistResult');
        if(!list){ list = document.createElement('div'); list.id='toplistResult'; document.querySelector('.toplist').appendChild(list); }
        list.innerHTML = '';
        if(top.length === 0){ top = [{priority:'low', issue:'{{TOP_EMPTY}}' }]; }
        top.forEach(function(t){
          var lv = t.priority === 'urgent' ? 'hi' : (t.priority === 'high' ? 'hi' : 'md');
          var row = document.createElement('div');
          row.className = 'row';
          row.innerHTML = '<span class="lv '+lv+'">'+t.priority+'</span>'+t.issue;
          list.appendChild(row);
        });
        var toplist = document.querySelector('.toplist');
        Array.prototype.slice.call(toplist.children).forEach(function(c){
          if(c.className && String(c.className).indexOf('row') !== -1 && !c.id){ toplist.removeChild(c); }
        });

        if(typeof window.__scanTotal === 'number'){
          window.__scanTotal += 1;
          var sc = document.getElementById('scanCount');
          if(sc) sc.textContent = window.__scanTotal;
        }
      })
      .catch(function(e){
        document.getElementById('rscore').textContent = '—';
        document.getElementById('demoNote').style.display = 'block';
        document.getElementById('demoNote').textContent = '{{CONNECT_ERR}}' + e;
      });
  }

  function startCheckout(){
    var u = document.getElementById('url').value.trim();
    var em = document.getElementById('email') ? document.getElementById('email').value.trim() : '';
    var note = document.getElementById('demoNote');
    function showNote(msg){ note.style.display='block'; note.textContent = msg; }
    if(!em){ showNote('{{EMAIL_REQ}}'); document.getElementById('email').focus(); return; }

    fetch('/api/order', {method:'POST', headers:{'Content-Type':'application/json'},
           body: JSON.stringify({url:u, customer_email:em})})
      .then(function(r){ return r.json().then(function(d){ return {ok:r.ok, json:d}; }); })
      .then(function(res){
        var d = res.json;
        if(!res.ok || d.error){
          showNote('{{ORDER_ERR}}' + (d.error || '{{UNKNOWN_ERR}}')); return;
        }
        var orderId = d.order_id;
        fetch('/api/create-checkout', {method:'POST', headers:{'Content-Type':'application/json'},
               body: JSON.stringify({url:u, order_id:orderId, price_usd:397})})
          .then(function(r){ return r.json(); })
          .then(function(cd){
            if(cd.redirect_url){ window.location.href = cd.redirect_url; return; }
            showNote('{{CHECKOUT_PRE}}' + orderId + '{{CHECKOUT_POST}}');
            document.getElementById('result').scrollIntoView({behavior:'smooth', block:'center'});
          })
          .catch(function(e){ showNote('{{CONNECT_CHECKOUT}}' + e); });
      })
      .catch(function(e){
        showNote('{{CONNECT_ORDER}}' + e);
      });
  }

  window.__scanTotal = 0;
  var sc = document.getElementById('scanCount');
  if(sc) sc.textContent = window.__scanTotal;

  document.addEventListener('keydown', function(e){ if(e.key==='Enter' && document.activeElement.id==='url') runScan(); });
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Per-language copy. (Locks: prices, 7-day guarantee, badges, scan wiring.)
# ---------------------------------------------------------------------------
def base(lang_attrib):
    return {
        "HTML_LANG": lang_attrib,
        "SEL_EN": "", "SEL_ZHH": "", "SEL_ZHS": "", "SEL_JA": "", "SEL_ES": "",
        "LOCKED": "Locked",
    }

EN = dict(base("en"), SEL_EN="selected", **{
    "TITLE": "AI SEO Audit Report — Free Scan Your Website | See Top Issues Instantly",
    "META_DESC": "Scan your website free and get an SEO score plus your Top 5 issues instantly. The full AI audit uncovers every SEO problem in one pass, auto-delivered in ~10 minutes.",
    "NAV_HOW": "How it works",
    "NAV_PRICE": "Pricing",
    "BADGE": "🤖 AI SEO Audit · Free Scan",
    "TB1": "Aligned with Google Search Essentials",
    "TB2": "Ahrefs×Semrush audit methodology",
    "TB3": "Official Core Web Vitals metrics",
    "H1_L1": "Your site's SEO,",
    "H1_EM": "scanned free",
    "H1_L3": " — see the issues instantly",
    "SUB": "Paste your website URL and get an SEO score + Top 5 issues in seconds. The full AI audit report shows you exactly how to fix them — no more guessing.",
    "INPUT_PLACEHOLDER": "Paste your website URL, e.g. mybusiness.com",
    "SCAN_BTN": "Scan My Site Free",
    "RESULT_TITLE": "Scan result:",
    "SCORE_LABEL": "SEO health score",
    "SCORE_HINT": "Scanning…",
    "TOP_LV": "mid",
    "TOP_PLACEHOLDER": "Enter your URL and click “Scan My Site Free” to see real data on your Top issues",
    "LOCK_FIXLIST": "Full <span class='fixCount'>—</span>-item fix list (updates after scan)",
    "LOCK_COMPETE": "Competitor comparison analysis",
    "LOCK_AI_STEPS": "AI step-by-step fix guide + prioritization",
    "EMAIL_NOTE": "Receive the report by email (full PDF delivery):",
    "CONSENT": "I agree my email is used only to deliver this report, as described in the Privacy Policy. I understand I can opt out anytime.",
    "UNLOCK_BTN": "Unlock Full Report — US$397",
    "GUARANTEE": "🛡️ 7-day peace-of-mind guarantee: full refund before delivery · free re-review after",
    "AUTO_DELIVER": "Auto-delivered to your email within ~10 minutes of payment",
    "TA": "🔒 100% free · no signup · instant result",
    "QUICK": "Want to try?",
    "STAT1_L": "Websites scanned",
    "STAT1_N": "0",
    "STAT2_L": "Reports hand-QC'd before delivery",
    "STAT2_N": "100%",
    "STAT3_N": "10 min",
    "STAT3_L": "report delivery",
    "HOW_H2": "3 free steps — see if your site has problems first",
    "HOW_SUB": "No signup, no credit card. Paste your URL.",
    "F1_T": "Paste your URL",
    "F1_D": "One input box. Paste your site address, click “Scan My Site Free”.",
    "F2_T": "Score + Top 5 instantly",
    "F2_D": "Get your SEO health score and the 5 most serious issues in seconds.",
    "F3_T": "Full report from US$397",
    "F3_D": "Unlock the full fix list when you're confident. Delivered instantly on payment.",
    "PRICE_H2": "Prove value free — the full version fixes your site",
    "PRICE_SUB": "Scan your site free first — see real problems before you decide. The “how to fix” lives in the full version.",
    "FREE_TAG": "Free",
    "FREE_1": "SEO health score",
    "FREE_2": "Top 5 most serious issues",
    "FREE_3": "Site type detection",
    "FREE_4": "Instant results",
    "FREE_CTA": "Scan Free",
    "PRO_TAG": "Full Version · Most Popular",
    "PRO_UNIT": "/ once",
    "PRO_PROMO": "Founder price for the first 50 — early-bird only, while spots last",
    "PRO_1": "Complete SEO issue fix list (count varies by site)",
    "PRO_2": "AI step-by-step fix guide + priority + expected impact",
    "PRO_3": "Competitor comparison analysis",
    "PRO_4": "Downloadable PDF report (white-label ready)",
    "PRO_5": "Auto-delivered within 10 minutes of payment",
    "PRO_6": "7-day guarantee: refund before delivery · free re-review after",
    "PRO_CTA": "Scan Free, then Unlock — US$397",
    "GROWTH_TAG": "Growth",
    "GROWTH_UNIT": "/ once",
    "GROWTH_1": "Everything in the full version",
    "GROWTH_2": "4 money-page deep dives (page-level)",
    "GROWTH_3": "Prioritized action roadmap",
    "GROWTH_4": "Competitor gap table",
    "GROWTH_5": "90-day execution roadmap",
    "GROWTH_6": "7-day guarantee",
    "GROWTH_CTA": "Scan Free, then see Growth",
    "PROOF_H2": "Know in seconds whether your site is healthy",
    "PROOF_SUB": "Scan your real website free — no sample site, no signup. Paste a URL and get your site's score and Top issues.",
    "URG_H2": "Scan free first — decide once you see real issues",
    "URG_P": "Founder price US$397 (was US$497) for the first 50 — back to full price once full. Scan free now, unlock if you love it.",
    "URG_CTA": "Scan My Site Free",
    "FOOT1": "SEO Scan.ai — AI SEO audit report · start with a 100% free scan",
    "FOOT_PRIVACY": "Privacy Policy",
    "FOOT_TERMS": "Terms of Service",
    "FOOT_REFUND": "Refund Policy",
    "FOOT_DISCLAIMER": "Disclaimer",
    "COPYRIGHT": "© 2026 SEO Scan.ai",
    "SCAN_ERR": "⚠️ Scan error: ",
    "HINT_GOOD": "✅ Healthy site",
    "HINT_MID": "⚠️ Worth improving",
    "HINT_BAD": "🔴 Many issues",
    "HINT_NODIAG": "Could not read diagnosis",
    "TOP_EMPTY": "No obvious technical errors detected",
    "CONNECT_ERR": "⚠️ Could not reach scan backend: ",
    "EMAIL_REQ": "⚠️ Please enter the email to receive the report (full PDF goes here)",
    "ORDER_ERR": "⚠️ Order failed: ",
    "UNKNOWN_ERR": "unknown error",
    "CHECKOUT_PRE": "💰 Order created (",
    "CHECKOUT_POST": "). Payment system preparing — this is the reserved checkout step. Once real Stripe is connected, “Unlock” will redirect to the Stripe payment page.",
    "CONNECT_CHECKOUT": "⚠️ Could not reach checkout server: ",
    "CONNECT_ORDER": "⚠️ Could not reach order server: ",
})

ZH_HANT = dict(base("zh-HK"), SEL_ZHH="selected", **{
    "TITLE": "AI SEO 審計報告 — 免費 Scan 你網站 | 即刻睇 Top 問題",
    "META_DESC": "免費 scan 你網站，即刻得到 SEO 總分同 Top 5 問題。完整 AI 審計報告一步發掘所有 SEO 隱患，約 10 分鐘自動交付。",
    "NAV_HOW": "點運作",
    "NAV_PRICE": "收費",
    "BADGE": "🤖 AI SEO 審計 · 免費 Scan 即睇",
    "TB1": "跟 Google Search Essentials 標準",
    "TB2": "Ahrefs×Semrush 審計方法",
    "TB3": "Core Web Vitals 官方指標",
    "H1_L1": "你網站嘅 SEO，",
    "H1_EM": "即刻免費 Scan",
    "H1_L3": "，睇到 Top 問題",
    "SUB": "貼你網站 URL，幾秒內得到 SEO 總分 + Top 5 問題。完整 AI 審計報告教你點樣修 —— 唔使再估。",
    "INPUT_PLACEHOLDER": "貼你網站 URL，例如 mybusiness.com",
    "SCAN_BTN": "免費 Scan 我網站",
    "RESULT_TITLE": "Scan 結果：",
    "SCORE_LABEL": "SEO 健康總分",
    "SCORE_HINT": "Scan 緊…",
    "TOP_LV": "中",
    "TOP_PLACEHOLDER": "輸入 URL 後撳「免費 Scan」睇真數據 Top 問題",
    "LOCK_FIXLIST": "完整 <span class='fixCount'>—</span> 項修復清單（Scan 後更新）",
    "LOCK_COMPETE": "同競爭對手對比分析",
    "LOCK_AI_STEPS": "AI 逐步修復指引 + 優先次序",
    "EMAIL_NOTE": "收報告 email（交付完整 PDF）：",
    "CONSENT": "我同意將 email 僅用於交付本報告（見私隱政策），可隨時取消訂閱。",
    "UNLOCK_BTN": "解鎖完整報告 — US$397",
    "GUARANTEE": "🛡️ 7 日放心保證：交付前全額退 · 交付後免費重審",
    "AUTO_DELIVER": "付款後約 10 分鐘內自動交付到 email",
    "TA": "🔒 100% 免費 · 無需註冊 · 掃一次即刻睇",
    "QUICK": "想試？",
    "STAT1_L": "網站已 Scan",
    "STAT1_N": "0",
    "STAT2_L": "每份報告人手 QC 後交付",
    "STAT2_N": "100%",
    "STAT3_N": "10 分鐘",
    "STAT3_L": "報告交付",
    "HOW_H2": "免費 3 步，先知道你網站有冇問題",
    "HOW_SUB": "唔使註冊、唔使信用卡。貼 URL 就得。",
    "F1_T": "貼上 URL",
    "F1_D": "一個輸入框，貼你網站網址，撳「免費 Scan」。",
    "F2_T": "即刻睇總分 + Top 5",
    "F2_D": "幾秒內得到 SEO 健康總分同最嚴重嘅 5 個問題。",
    "F3_T": "完整報告先 US$397",
    "F3_D": "有信心中意先解鎖完整修復清單。付款即時交付。",
    "PRICE_H2": "免費證明價值，完整版幫你執好個網站",
    "PRICE_SUB": "先免費 scan 你個網站——見到真問題先決定。「點改」留俾完整版。",
    "FREE_TAG": "免費",
    "FREE_1": "SEO 健康總分",
    "FREE_2": "Top 5 最嚴重問題",
    "FREE_3": "網站類型識別",
    "FREE_4": "即時睇即時攞",
    "FREE_CTA": "免費 Scan",
    "PRO_TAG": "完整版 · 最受歡迎",
    "PRO_UNIT": "/ 一次",
    "PRO_PROMO": "首 50 位創始價（只限早鳥，名額派完即止）",
    "PRO_1": "完整 SEO 問題修復清單（數量因網站而異）",
    "PRO_2": "AI 逐步修復指引 + 優先次序 + 預期效果",
    "PRO_3": "同競爭對手對比分析",
    "PRO_4": "可下載 PDF 報告（白牌可用）",
    "PRO_5": "付款後 10 分鐘內自動交付",
    "PRO_6": "7 日放心保證：交付前可退 · 交付後免費重審",
    "PRO_CTA": "免費 Scan 後解鎖 — US$397",
    "GROWTH_TAG": "進階",
    "GROWTH_UNIT": "/ 一次",
    "GROWTH_1": "完整版全部内容",
    "GROWTH_2": "4 條錢頁 page-level 深挖",
    "GROWTH_3": "優先次序行動路線圖",
    "GROWTH_4": "競爭對手差距表",
    "GROWTH_5": "90 日執行 roadmap",
    "GROWTH_6": "7 日放心保證",
    "GROWTH_CTA": "免費 Scan 後睇 Growth",
    "PROOF_H2": "你個網站，即刻知有冇問題",
    "PROOF_SUB": "免費 scan 你個真實網站——唔使樣本、唔使註冊，貼 URL 就出你網站嘅總分同 Top 問題。",
    "URG_H2": "先免費 scan，見到真問題先決定",
    "URG_P": "首 50 位創始價 US$397（原價 US$497）—— 額滿即回復正價。而家免費 scan，中意先解鎖。",
    "URG_CTA": "免費 Scan 我網站",
    "FOOT1": "SEO Scan.ai — AI SEO 審計報告 · 100% 免費 Scan 入門",
    "FOOT_PRIVACY": "私隱政策",
    "FOOT_TERMS": "使用條款",
    "FOOT_REFUND": "退款政策",
    "FOOT_DISCLAIMER": "免責聲明",
    "COPYRIGHT": "© 2026 SEO Scan.ai",
    "SCAN_ERR": "⚠️ 掃描出錯：",
    "HINT_GOOD": "✅ 健康網站",
    "HINT_MID": "⚠️ 值得改進",
    "HINT_BAD": "🔴 好多問題",
    "HINT_NODIAG": "未能讀取診斷",
    "TOP_EMPTY": "未能偵測到明顯技術錯誤",
    "CONNECT_ERR": "⚠️ 連唔到 scan 後端：",
    "EMAIL_REQ": "⚠️ 請輸入收報告嘅 email（完整 PDF 會寄去呢度）",
    "ORDER_ERR": "⚠️ 落單失敗：",
    "UNKNOWN_ERR": "未知錯誤",
    "CHECKOUT_PRE": "💰 訂單已建立（",
    "CHECKOUT_POST": "）。付款系統準備中 —— 呢個係預留步伐（checkout_placeholder）。接完真 Stripe 之後，撳「解鎖」會自動跳去 Stripe 付款頁。",
    "CONNECT_CHECKOUT": "⚠️ 連唔到結帳伺服器：",
    "CONNECT_ORDER": "⚠️ 連唔到落單伺服器：",
})

ZH_HANS = dict(base("zh-CN"), SEL_ZHS="selected", **{
    "TITLE": "AI SEO 审计报告 — 免费扫描你的网站 | 立即查看关键问题",
    "META_DESC": "免费扫描你的网站，立即获得 SEO 总分和 Top 5 问题。完整 AI 审计报告一步发掘所有 SEO 隐患，约 10 分钟自动交付。",
    "NAV_HOW": "运行方式",
    "NAV_PRICE": "定价",
    "BADGE": "🤖 AI SEO 审计 · 免费扫描即看",
    "TB1": "符合 Google Search Essentials 标准",
    "TB2": "Ahrefs×Semrush 审计方法",
    "TB3": "Core Web Vitals 官方指标",
    "H1_L1": "你网站的 SEO，",
    "H1_EM": "立即免费扫描",
    "H1_L3": "，看到关键问题",
    "SUB": "粘贴你的网站 URL，几秒内获得 SEO 总分 + 前 5 大问题。完整 AI 审计报告教你如何修复 —— 不用再猜。",
    "INPUT_PLACEHOLDER": "粘贴你的网站 URL，例如 mybusiness.com",
    "SCAN_BTN": "免费扫描我的网站",
    "RESULT_TITLE": "扫描结果：",
    "SCORE_LABEL": "SEO 健康总分",
    "SCORE_HINT": "扫描中…",
    "TOP_LV": "中",
    "TOP_PLACEHOLDER": "输入 URL 后点击「免费扫描」，查看你网站的 Top 问题",
    "LOCK_FIXLIST": "完整 <span class='fixCount'>—</span> 项修复清单（扫描后更新）",
    "LOCK_COMPETE": "与竞争对手对比分析",
    "LOCK_AI_STEPS": "AI 分步修复指引 + 优先级",
    "EMAIL_NOTE": "通过 email 接收报告（交付完整 PDF）：",
    "CONSENT": "我同意将 email 仅用于交付本报告（见隐私政策），可随时取消订阅。",
    "UNLOCK_BTN": "解锁完整报告 — US$397",
    "GUARANTEE": "🛡️ 7 日安心保证：交付前全额退款 · 交付后免费复审",
    "AUTO_DELIVER": "付款后约 10 分钟内自动交付到 email",
    "TA": "🔒 100% 免费 · 无需注册 · 扫码即看",
    "QUICK": "想试试？",
    "STAT1_L": "已扫描网站",
    "STAT1_N": "0",
    "STAT2_L": "每份报告人手质检后交付",
    "STAT2_N": "100%",
    "STAT3_N": "10 分钟",
    "STAT3_L": "报告交付",
    "HOW_H2": "免费 3 步，先了解网站有没有问题",
    "HOW_SUB": "无需注册、无需信用卡。粘贴 URL 即可。",
    "F1_T": "粘贴 URL",
    "F1_D": "一个输入框，粘贴你的网站地址，点击「免费扫描」。",
    "F2_T": "立即查看总分 + Top 5",
    "F2_D": "几秒内获得 SEO 健康总分和最严重的 5 大问题。",
    "F3_T": "完整报告 US$397 起",
    "F3_D": "有信心再解锁完整修复清单。付款即时交付。",
    "PRICE_H2": "免费证明价值，完整版帮你修好网站",
    "PRICE_SUB": "先免费扫描你的网站——看到真实问题再决定。「怎么改」留给完整版。",
    "FREE_TAG": "免费",
    "FREE_1": "SEO 健康总分",
    "FREE_2": "前 5 大最严重问题",
    "FREE_3": "网站类型识别",
    "FREE_4": "即扫即得",
    "FREE_CTA": "免费扫描",
    "PRO_TAG": "完整版 · 最受欢迎",
    "PRO_UNIT": "/ 一次",
    "PRO_PROMO": "前 50 位创始价（仅限早鸟，名额发完即止）",
    "PRO_1": "完整 SEO 问题修复清单（数量因网站而异）",
    "PRO_2": "AI 分步修复指引 + 优先级 + 预期效果",
    "PRO_3": "与竞争对手对比分析",
    "PRO_4": "可下载 PDF 报告（白标可用）",
    "PRO_5": "付款后 10 分钟内自动交付",
    "PRO_6": "7 日安心保证：交付前可退 · 交付后免费复审",
    "PRO_CTA": "免费扫描后解锁 — US$397",
    "GROWTH_TAG": "进阶",
    "GROWTH_UNIT": "/ 一次",
    "GROWTH_1": "包含完整版全部内容",
    "GROWTH_2": "4 条转化页 page-level 深挖",
    "GROWTH_3": "优先级行动路线图",
    "GROWTH_4": "竞争对手差距表",
    "GROWTH_5": "90 日执行路线图",
    "GROWTH_6": "7 日安心保证",
    "GROWTH_CTA": "免费扫描后查看 Growth",
    "PROOF_H2": "你的网站有没有问题，立即知道",
    "PROOF_SUB": "免费扫描你的真实网站——无需样本、无需注册，粘贴 URL 即可看到你的网站总分和关键问题。",
    "URG_H2": "先免费扫描，看到真实问题再决定",
    "URG_P": "前 50 位创始价 US$397（原价 US$497）—— 名额满即恢复原价。现在免费扫描，满意再解锁。",
    "URG_CTA": "免费扫描我的网站",
    "FOOT1": "SEO Scan.ai — AI SEO 审计报告 · 100% 免费扫描入门",
    "FOOT_PRIVACY": "隐私政策",
    "FOOT_TERMS": "服务条款",
    "FOOT_REFUND": "退款政策",
    "FOOT_DISCLAIMER": "免责声明",
    "COPYRIGHT": "© 2026 SEO Scan.ai",
    "SCAN_ERR": "⚠️ 扫描出错：",
    "HINT_GOOD": "✅ 健康网站",
    "HINT_MID": "⚠️ 值得改进",
    "HINT_BAD": "🔴 问题较多",
    "HINT_NODIAG": "未能读取诊断",
    "TOP_EMPTY": "未检测到明显技术错误",
    "CONNECT_ERR": "⚠️ 无法连接到扫描后端：",
    "EMAIL_REQ": "⚠️ 请输入接收报告的 email（完整 PDF 会发送到这里）",
    "ORDER_ERR": "⚠️ 下单失败：",
    "UNKNOWN_ERR": "未知错误",
    "CHECKOUT_PRE": "💰 订单已创建（",
    "CHECKOUT_POST": "）。支付系统准备中 —— 这是预留步骤（checkout_placeholder）。接入真实 Stripe 后，点击「解锁」会自动跳转到 Stripe 支付页。",
    "CONNECT_CHECKOUT": "⚠️ 无法连接到结账服务器：",
    "CONNECT_ORDER": "⚠️ 无法连接到下单服务器：",
})

JA = dict(base("ja"), SEL_JA="selected", **{
    "TITLE": "AI SEO監査レポート — サイトを無料スキャン | 重要な問題を即確認",
    "META_DESC": "あなたのサイトを無料スキャンし、SEOスコアとTop5の問題を即座に取得。完全なAI監査でSEOの問題を一挙に洗い出し、約10分で自動納品。",
    "NAV_HOW": "仕組み",
    "NAV_PRICE": "料金",
    "BADGE": "🤖 AI SEO監査 · 無料スキャン",
    "TB1": "Google Search Essentials 準拠",
    "TB2": "Ahrefs×Semrush 監査手法",
    "TB3": "Core Web Vitals 公式指標",
    "H1_L1": "あなたのサイトのSEOを、",
    "H1_EM": "無料でスキャン",
    "H1_L3": "して問題を即確認",
    "SUB": "サイトURLを貼るだけで、数秒でSEOスコアとTop5の問題を取得。完全なAI監査レポートが直し方まで案内します —— もう推測する必要はありません。",
    "INPUT_PLACEHOLDER": "サイトのURLを貼り付け（例：mybusiness.com）",
    "SCAN_BTN": "サイトを無料スキャン",
    "RESULT_TITLE": "スキャン結果：",
    "SCORE_LABEL": "SEOヘルススコア",
    "SCORE_HINT": "スキャン中…",
    "TOP_LV": "中位",
    "TOP_PLACEHOLDER": "URLを入力して「無料スキャン」を押すと、実際のデータでTop問題を確認",
    "LOCK_FIXLIST": "完全な<span class='fixCount'>—</span>項目の修正リスト（スキャン後に更新）",
    "LOCK_COMPETE": "競合他社との比較分析",
    "LOCK_AI_STEPS": "AIによるステップ別修正ガイド + 優先順位",
    "EMAIL_NOTE": "レポートをemailで受け取る（完全版PDFを納品）：",
    "CONSENT": "本報告書の配信のためだけにメールを使用することに同意します（プライバシーポリシー参照）。いつでも登録解除できます。",
    "UNLOCK_BTN": "完全レポートを解除 — US$397",
    "GUARANTEE": "🛡️ 7日間の安心保証：納品前に全額返金 · 納品後に無料で再審査",
    "AUTO_DELIVER": "支払い後約10分でメールに自動送信",
    "TA": "🔒 100%無料 · 登録不要 · スキャンして即確認",
    "QUICK": "試してみますか？",
    "STAT1_L": "スキャン済みサイト",
    "STAT1_N": "0",
    "STAT2_L": "全レポートを人手QC後に納品",
    "STAT2_N": "100%",
    "STAT3_N": "10分",
    "STAT3_L": "レポート納品",
    "HOW_H2": "無料の3ステップ — まずサイトに問題がないか確認",
    "HOW_SUB": "登録不要、クレジットカード不要。URLを貼るだけ。",
    "F1_T": "URLを貼る",
    "F1_D": "1つの入力欄にサイトアドレスを貼り、「無料スキャン」をクリック。",
    "F2_T": "スコアとTop5を即確認",
    "F2_D": "数秒でSEOヘルススコアと最も深刻な5つの問題を取得。",
    "F3_T": "完全レポートはUS$397から",
    "F3_D": "納得してから完全な修正リストを解除。支払いと同時に即納品。",
    "PRICE_H2": "無料で価値を証明、完全版でサイトを改善",
    "PRICE_SUB": "先に無料でサイトをスキャン —— 実際の問題を見てから判断。「直し方」は完全版にあります。",
    "FREE_TAG": "無料",
    "FREE_1": "SEOヘルススコア",
    "FREE_2": "最も深刻なTop5の問題",
    "FREE_3": "サイト種別の検出",
    "FREE_4": "即座に結果を確認",
    "FREE_CTA": "無料スキャン",
    "PRO_TAG": "完全版 · 最も人気",
    "PRO_UNIT": "/ 1回",
    "PRO_PROMO": "先着50名の創業者価格（限定先行・枠が埋まり次第終了）",
    "PRO_1": "完全なSEO修正リスト（件数はサイトにより異なります）",
    "PRO_2": "AIによるステップ別修正ガイド + 優先順位 + 期待効果",
    "PRO_3": "競合他社との比較分析",
    "PRO_4": "ダウンロード可能なPDFレポート（ホワイトラベル対応）",
    "PRO_5": "支払い後10分以内に自動納品",
    "PRO_6": "7日間保証：納品前に返金可 · 納品後に無料再審査",
    "PRO_CTA": "無料スキャン後に解除 — US$397",
    "GROWTH_TAG": "発展ステージ",
    "GROWTH_UNIT": "/ 1回",
    "GROWTH_1": "完全版の全コンテンツ",
    "GROWTH_2": "4つのマネーぺージをページレベルで深掘り",
    "GROWTH_3": "優先順位付きアクションロードマップ",
    "GROWTH_4": "競合とのギャップ表",
    "GROWTH_5": "90日間の実行ロードマップ",
    "GROWTH_6": "7日間の安心保証",
    "GROWTH_CTA": "無料スキャン後にGrowthを確認",
    "PROOF_H2": "サイトが健康か、数秒で分かる",
    "PROOF_SUB": "あなたの実際のサイトを無料でスキャン —— サンプル不要、登録不要。URLを貼るだけで、あなたのサイトのスコアとTop問題を取得。",
    "URG_H2": "先に無料スキャン — 実問題を見てから決定",
    "URG_P": "先着50名の創業者価格US$397（通常US$497）—— 枠が埋まれば通常価格に戻ります。今すぐ無料スキャン、気に入ったら解除。",
    "URG_CTA": "サイトを無料スキャン",
    "FOOT1": "SEO Scan.ai — AI SEO監査レポート · 100%無料スキャンから開始",
    "FOOT_PRIVACY": "プライバシーポリシー",
    "FOOT_TERMS": "利用規約",
    "FOOT_REFUND": "返金ポリシー",
    "FOOT_DISCLAIMER": "免責事項",
    "COPYRIGHT": "© 2026 SEO Scan.ai",
    "SCAN_ERR": "⚠️ スキャンエラー：",
    "HINT_GOOD": "✅ 健全なサイト",
    "HINT_MID": "⚠️ 改善の余地あり",
    "HINT_BAD": "🔴 問題が多い",
    "HINT_NODIAG": "診断を読み取れません",
    "TOP_EMPTY": "明確な技術エラーは検出されませんでした",
    "CONNECT_ERR": "⚠️ スキャンサーバーに接続できません：",
    "EMAIL_REQ": "⚠️ レポート受信用のemailを入力してください（完全版PDFが届きます）",
    "ORDER_ERR": "⚠️ 注文に失敗しました：",
    "UNKNOWN_ERR": "不明なエラー",
    "CHECKOUT_PRE": "💰 注文を作成しました（",
    "CHECKOUT_POST": "）。決済システム準備中 —— これは予約済みのチェックアウト手順（checkout_placeholder）です。実際のStripe接続後、「解除」を押すとStripeの支払いページに自動で遷移します。",
    "CONNECT_CHECKOUT": "⚠️ チェックアウトサーバーに接続できません：",
    "CONNECT_ORDER": "⚠️ 注文サーバーに接続できません：",
})

ES = dict(base("es"), SEL_ES="selected", **{
    "TITLE": "Informe de Auditoría SEO con IA — Escanea tu web gratis | Ve los problemas clave al instante",
    "META_DESC": "Escanea tu web gratis y obtén al instante una puntuación SEO y tus 5 problemas principales. La auditoría IA completa descubre todos los problemas SEO de una pasada, con entrega automática en unos 10 minutos.",
    "NAV_HOW": "Cómo funciona",
    "NAV_PRICE": "Precios",
    "BADGE": "🤖 Auditoría SEO con IA · Escaneo gratis",
    "TB1": "Alineado con Google Search Essentials",
    "TB2": "Metodología de auditoría Ahrefs×Semrush",
    "TB3": "Métricas oficiales de Core Web Vitals",
    "H1_L1": "El SEO de tu web,",
    "H1_EM": "escanéalo gratis",
    "H1_L3": " — mira los problemas al instante",
    "SUB": "Pega el URL de tu web y obtén en segundos una puntuación SEO + tus 5 problemas principales. El informe completo de auditoría IA te muestra exactamente cómo arreglarlos — sin más adivinanzas.",
    "INPUT_PLACEHOLDER": "Pega el URL de tu web, p. ej. mybusiness.com",
    "SCAN_BTN": "Escanear mi web gratis",
    "RESULT_TITLE": "Resultado del escaneo:",
    "SCORE_LABEL": "Puntuación de salud SEO",
    "SCORE_HINT": "Escaneando…",
    "TOP_LV": "medio",
    "TOP_PLACEHOLDER": "Introduce el URL y pulsa «Escanear mi web gratis» para ver tus Top problemas en datos reales",
    "LOCK_FIXLIST": "Lista de <span class='fixCount'>—</span> correcciones (se actualiza tras el escaneo)",
    "LOCK_COMPETE": "Análisis comparativo con la competencia",
    "LOCK_AI_STEPS": "Guía de arreglo paso a paso con IA + priorización",
    "EMAIL_NOTE": "Recibe el informe por email (entrega del PDF completo):",
    "CONSENT": "Acepto que mi email se use solo para entregar este informe (ver Política de Privacidad). Puedo darme de baja en cualquier momento.",
    "UNLOCK_BTN": "Desbloquear Informe Completo — US$397",
    "GUARANTEE": "🛡️ Garantía de 7 días: reembolso total antes de la entrega · revisión gratuita después",
    "AUTO_DELIVER": "Entrega automática a tu email en unos 10 minutos tras el pago",
    "TA": "🔒 100% gratis · sin registro · resultado al instante",
    "QUICK": "¿Quieres probar?",
    "STAT1_L": "Sitios escaneados",
    "STAT1_N": "0",
    "STAT2_L": "Informes QC-ed a mano antes de enviar",
    "STAT2_N": "100%",
    "STAT3_N": "10 min",
    "STAT3_L": "entrega del informe",
    "HOW_H2": "3 pasos gratis — comprueba primero si tu web tiene problemas",
    "HOW_SUB": "Sin registro ni tarjeta de crédito. Solo pega tu URL.",
    "F1_T": "Pega tu URL",
    "F1_D": "Un solo campo. Pega la dirección de tu web y pulsa «Escanear mi web gratis».",
    "F2_T": "Puntuación + Top 5 al instante",
    "F2_D": "Obtén tu puntuación de salud SEO y los 5 problemas más graves en segundos.",
    "F3_T": "Informe completo desde US$397",
    "F3_D": "Desbloquea la lista completa cuando estés seguro. Entrega inmediata al pagar.",
    "PRICE_H2": "Prueba el valor gratis — la versión completa arregla tu web",
    "PRICE_SUB": "Escanea tu web gratis primero — ve los problemas reales antes de decidir. El «cómo arreglarlo» está en la versión completa.",
    "FREE_TAG": "Gratis",
    "FREE_1": "Puntuación de salud SEO",
    "FREE_2": "5 problemas más graves",
    "FREE_3": "Detección del tipo de sitio",
    "FREE_4": "Resultados al instante",
    "FREE_CTA": "Escaneo Gratis",
    "PRO_TAG": "Versión Completa · Más Popular",
    "PRO_UNIT": "/ una vez",
    "PRO_PROMO": "Precio fundador para los primeros 50 — solo preventa, hasta agotar plazas",
    "PRO_1": "Lista completa de correcciones SEO (el número varía según el sitio)",
    "PRO_2": "Guía de arreglo paso a paso con IA + prioridad + impacto esperado",
    "PRO_3": "Análisis comparativo con la competencia",
    "PRO_4": "Informe PDF descargable (listo para marca blanca)",
    "PRO_5": "Entrega automática en menos de 10 minutos tras el pago",
    "PRO_6": "Garantía de 7 días: reembolso antes de la entrega · revisión gratuita después",
    "PRO_CTA": "Escanea gratis, luego Desbloquea — US$397",
    "GROWTH_TAG": "Crecimiento",
    "GROWTH_UNIT": "/ una vez",
    "GROWTH_1": "Todo lo de la versión completa",
    "GROWTH_2": "4 análisis a fondo de páginas clave (a nivel página)",
    "GROWTH_3": "Hoja de ruta de acciones priorizada",
    "GROWTH_4": "Tabla de diferencias con la competencia",
    "GROWTH_5": "Plan de ejecución a 90 días",
    "GROWTH_6": "Garantía de 7 días",
    "GROWTH_CTA": "Escanea gratis, luego ve Growth",
    "PROOF_H2": "Descubre en segundos si tu web está sana",
    "PROOF_SUB": "Escanea tu web real gratis — sin sitio de muestra, sin registro. Pega un URL y obtén la puntuación y los Top problemas de tu sitio.",
    "URG_H2": "Escanea gratis primero — decide al ver problemas reales",
    "URG_P": "Precio fundador US$397 (antes US$497) para los primeros 50 — vuelve al precio normal al llenarse. Escanea gratis ahora, desbloquea si te encanta.",
    "URG_CTA": "Escanear mi web gratis",
    "FOOT1": "SEO Scan.ai — informe de auditoría SEO con IA · empieza con un escaneo 100% gratis",
    "FOOT_PRIVACY": "Política de Privacidad",
    "FOOT_TERMS": "Términos del Servicio",
    "FOOT_REFUND": "Política de Reembolso",
    "FOOT_DISCLAIMER": "Aviso Legal",
    "COPYRIGHT": "© 2026 SEO Scan.ai",
    "SCAN_ERR": "⚠️ Error al escanear: ",
    "HINT_GOOD": "✅ Sitio sano",
    "HINT_MID": "⚠️ Mejorable",
    "HINT_BAD": "🔴 Muchos problemas",
    "HINT_NODIAG": "No se pudo leer el diagnóstico",
    "TOP_EMPTY": "No se detectaron errores técnicos evidentes",
    "CONNECT_ERR": "⚠️ No se pudo conectar con el backend de escaneo: ",
    "EMAIL_REQ": "⚠️ Introduce el email para recibir el informe (el PDF completo llega aquí)",
    "ORDER_ERR": "⚠️ Error en el pedido: ",
    "UNKNOWN_ERR": "error desconocido",
    "CHECKOUT_PRE": "💰 Pedido creado (",
    "CHECKOUT_POST": "). Sistema de pago en preparación — este es el paso reservado (checkout_placeholder). Una vez conectado el Stripe real, pulsar «Desbloquear» te redirigirá a la página de pago de Stripe.",
    "CONNECT_CHECKOUT": "⚠️ No se pudo conectar con el servidor de pago: ",
    "CONNECT_ORDER": "⚠️ No se pudo conectar con el servidor de pedidos: ",
})

LANGS = {
    "landing_page.html":        EN,          # English MASTER = default at /
    "landing_en.html":          EN,
    "landing_zh-Hant.html":     ZH_HANT,
    "landing_zh-Hans.html":     ZH_HANS,
    "landing_ja.html":          JA,
    "landing_es.html":          ES,
}

def render(tokens):
    html = SKELETON
    # per-language site base + URL path are appended by main(); keep URL tokens in place
    for k, v in tokens.items():
        html = html.replace("{{" + k + "}}", v)
    # safety: any leftover token -> flag (exclude URL tokens handled by main())
    import re
    leftovers = re.findall(r"\{\{[A-Z0-9_]+\}\}", html)
    leftovers = [x for x in leftovers if x not in ("{{URL_PATH}}", "{{BASE_URL}}")]
    if leftovers:
        raise RuntimeError("Missing tokens: " + ", ".join(sorted(set(leftovers))))
    return html


def main():
    BASE = "https://seoscanaudit.com"
    # per-file URL path so canonical/hreflang point to the right locale URL
    URL_PATHS = {
        "landing_page.html": "", "landing_en.html": "",
        "landing_zh-Hant.html": "zh-Hant", "landing_zh-Hans.html": "zh-Hans",
        "landing_ja.html": "ja", "landing_es.html": "es",
    }
    for fname, tokens in LANGS.items():
        html = render(tokens)
        up = URL_PATHS.get(fname, "")
        # replace URL tokens AFTER render() so they're not flagged as leftovers
        html = html.replace("{{URL_PATH}}", up)
        html = html.replace("{{BASE_URL}}", BASE)
        path = os.path.join(HERE, fname)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"wrote {fname} ({len(html)} bytes)")


if __name__ == "__main__":
    main()