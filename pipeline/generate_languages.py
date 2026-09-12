#!/usr/bin/env python3
"""generate_languages.py — 產生 6 個 landing 檔（EN master + 5 語言）。

Quiet Authority redesign v1 (2026-09-12)。
- 每個檔都係完整 self-contained HTML，保留所有完現 JS (runScan/startCheckout/
  chooseProduct/langSel) + 付款/language flow。
- 價格由 {{PRICE_USD}} / {{EARLY_PRICE_USD}} / {{GROWTH_PRICE_USD}} / {{REGULAR_PRICE_USD}}
  填入（config 單一來源）。
- EN = master 語源，其餘語言用 dict 翻譯。

安全：呢個檔只係「產生」工具；改完之後必須 re-run —— python3 generate_languages.py
重新寫出 6 個檔，先可以由 server 服務到新設計。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

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
    --bg:#F7F7F5; --ink:#0B1220; --navy:#0B1220; --muted:#657085;
    --indigo:#4F46E5; --indigo-dark:#4338CA; --teal:#0F9D8A; --amber:#D97706;
    --card:#FFFFFF; --line:#E3E7ED; --line-subtle:#EDEFF2;
    --shadow:0 1px 2px rgba(11,18,32,.04), 0 10px 28px -14px rgba(11,18,32,.16);
    --radius:14px;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html{scroll-behavior:smooth}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang HK","Microsoft JhengHei","Microsoft YaHei","Hiragino Sans","Noto Sans SC","Noto Sans JP","Noto Sans",sans-serif;
    color:var(--ink);background:var(--bg);line-height:1.6;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
  a{color:var(--indigo)}
  .wrap{max-width:1100px;margin:0 auto;padding:0 28px}
  .topnav{display:flex;justify-content:space-between;align-items:center;padding:20px 0;gap:16px;flex-wrap:wrap}
  .logo{font-size:20px;font-weight:800;letter-spacing:-.3px;color:var(--ink)}
  .logo span{color:var(--indigo)}
  .nav-links{display:flex;gap:22px;align-items:center;flex-wrap:wrap}
  .nav-links a{color:var(--muted);text-decoration:none;font-weight:600;font-size:15px;transition:color .15s}
  .nav-links a:hover{color:var(--indigo)}
  .langbox select{appearance:none;background:#fff;border:1px solid var(--line);border-radius:10px;
    padding:8px 32px 8px 14px;font-size:14px;color:var(--ink);cursor:pointer;font-weight:600;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path d='M0 0l5 6 5-6z' fill='%23657085'/></svg>");
    background-repeat:no-repeat;background-position:right 12px center;outline:none}
  .langbox select:focus-visible{outline:2px solid var(--indigo);outline-offset:2px}
  .eyebrow{display:inline-block;font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--indigo);margin-bottom:16px}
  h1{font-size:clamp(32px,5vw,52px);line-height:1.08;font-weight:800;letter-spacing:-1px;margin-bottom:20px}
  .lead{font-size:clamp(16px,2vw,19px);color:var(--muted);max-width:600px;line-height:1.65}
  .hero{display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:center;padding:64px 0 72px}
  .hero-cta{display:flex;gap:14px;flex-wrap:wrap;margin-top:30px}
  .btn{display:inline-flex;align-items:center;justify-content:center;border:none;cursor:pointer;
    font-weight:700;padding:16px 28px;border-radius:12px;font-size:16px;text-decoration:none;
    transition:background .16s,transform .05s;line-height:1}
  .btn:active{transform:translateY(1px)}
  .btn-primary{background:var(--indigo);color:#fff}
  .btn-primary:hover{background:var(--indigo-dark)}
  .btn-secondary{background:#fff;color:var(--ink);border:1px solid var(--line)}
  .btn-secondary:hover{background:var(--line-subtle)}
  .btn:focus-visible{outline:2px solid var(--indigo);outline-offset:2px}
  .micro{font-size:13px;color:var(--muted);margin-top:18px}
  .micro b{color:var(--teal)}
  .preview{border:1px solid var(--line);border-radius:18px;background:var(--card);box-shadow:var(--shadow);overflow:hidden}
  .preview-head{display:flex;align-items:center;justify-content:space-between;padding:18px 22px;border-bottom:1px solid var(--line);background:#fbfbfa}
  .preview-head .pill{font-size:13px;font-weight:800;color:var(--indigo)}
  .preview-head .lbl{font-size:12px;color:var(--muted)}
  .preview-body{padding:24px 22px;display:flex;flex-direction:column;gap:18px}
  .pv-block{background:var(--bg);border:1px solid var(--line-subtle);border-radius:12px;padding:18px}
  .pv-block h4{font-size:13px;font-weight:800;color:var(--ink);margin-bottom:8px;letter-spacing:.2px}
  .pv-row{display:flex;gap:10px;align-items:center;font-size:13px;color:var(--muted);padding:5px 0}
  .pv-row .chk{color:var(--teal);font-weight:800}
  .pv-badge{font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;margin-left:auto}
  .pv-badge.p0{background:#fdecec;color:#c0392b}
  .pv-badge.p1{background:#eceefb;color:var(--indigo)}
  section{padding:72px 0}
  .section-head{text-align:center;max-width:680px;margin:0 auto 44px}
  .section-head .eyebrow{margin-bottom:10px}
  .section-head h2{font-size:clamp(26px,3.4vw,36px);font-weight:800;letter-spacing:-.6px;line-height:1.15}
  .section-head p{color:var(--muted);margin-top:12px;font-size:16px}
  .grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
  .feat-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:24px;box-shadow:0 1px 2px rgba(11,18,32,.03)}
  .feat-card .tick{width:34px;height:34px;border-radius:10px;background:#eaf6f4;color:var(--teal);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:17px;margin-bottom:14px}
  .feat-card h4{font-size:16px;font-weight:700;margin-bottom:6px}
  .feat-card p{font-size:14px;color:var(--muted)}
  .process{background:var(--navy);color:#fff}
  .process .section-head h2{color:#fff}
  .process .section-head p{color:#aab4c5}
  .process-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;counter-reset:step}
  .step{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:24px}
  .step .num{font-size:12px;font-weight:800;color:var(--teal);letter-spacing:1px;margin-bottom:10px}
  .step h4{font-size:16px;font-weight:700;margin-bottom:6px;color:#fff}
  .step p{font-size:13px;color:#aab4c5;line-height:1.5}
  .pricing-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;max-width:880px;margin:0 auto}
  .pcard{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:32px;position:relative;display:flex;flex-direction:column;box-shadow:0 1px 2px rgba(11,18,32,.03)}
  .pcard.highlight{border:1.5px solid var(--indigo);box-shadow:var(--shadow)}
  .pcard .who{font-size:14px;color:var(--muted);margin:8px 0 18px;line-height:1.5}
  .pcard .price{font-size:40px;font-weight:800;letter-spacing:-1px;margin-bottom:18px}
  .pcard .price small{font-size:14px;color:var(--muted);font-weight:500;letter-spacing:0}
  .pcard ul{list-style:none;margin:0 0 8px}
  .pcard li{padding:7px 0;font-size:14.5px;display:flex;gap:10px;align-items:flex-start}
  .pcard li .chk{color:var(--teal);font-weight:800;flex-shrink:0;margin-top:1px}
  .pcard .cta{margin-top:auto;padding-top:22px}
  .badge-hi{position:absolute;top:-13px;left:32px;background:var(--indigo);color:#fff;font-size:12px;font-weight:700;padding:6px 14px;border-radius:999px;letter-spacing:.2px}
  .trust{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;max-width:980px;margin:0 auto}
  .trust-item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
  .trust-item b{font-size:14px;display:block;margin-bottom:4px}
  .trust-item span{font-size:13px;color:var(--muted)}
  .final-cta{background:var(--navy);color:#fff;text-align:center;padding:80px 0}
  .final-cta h2{font-size:clamp(28px,4vw,42px);font-weight:800;letter-spacing:-.6px;max-width:640px;margin:0 auto 20px}
  .final-cta .btn{margin-top:12px}
  .result{display:none;max-width:620px;margin:26px auto 0;background:#fff;border:1px solid var(--line);border-radius:16px;padding:24px;box-shadow:var(--shadow);text-align:left}
  .result h3{font-size:18px;margin-bottom:12px}
  .demoNote{display:none;background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;font-size:13px;padding:8px 12px;border-radius:10px;margin-bottom:14px;line-height:1.5}
  .score{display:flex;align-items:center;gap:18px;margin-bottom:6px}
  .ring{width:74px;height:74px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:22px;color:#fff;background:conic-gradient(var(--indigo) 62%,var(--line) 0)}
  .ring span{background:#fff;border-radius:50%;width:58px;height:58px;display:flex;align-items:center;justify-content:center;color:var(--ink)}
  .toplist{margin-top:16px}
  .toplist .row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--line);font-size:14px}
  .toplist .lv{font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px}
  .lv.hi{background:#fdecec;color:#c0392b}
  .lv.md{background:#fef3c7;color:var(--amber)}
  .lockrow{display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px dashed var(--line);color:var(--muted);font-size:14px;cursor:pointer}
  .unlock{background:var(--indigo);color:#fff;border:none;cursor:pointer;font-weight:800;padding:18px;border-radius:12px;font-size:17px;width:100%;margin-top:18px;transition:background .16s}
  .unlock:hover{background:var(--indigo-dark)}
  .scanbox{background:#fff;max-width:620px;margin:30px 0 0;padding:10px;border-radius:14px;box-shadow:var(--shadow);display:flex;gap:8px;border:1px solid var(--line)}
  .scanbox input{flex:1;border:none;outline:none;padding:15px 16px;font-size:16px;color:var(--ink);border-radius:10px;background:var(--bg);min-width:0}
  .scanbox input:focus{outline:2px solid var(--indigo);outline-offset:-1px}
  .scanbox input::placeholder{color:#94a3b8}
  .scanbox button{border:none;cursor:pointer;background:var(--indigo);color:#fff;font-weight:700;padding:15px 22px;border-radius:10px;font-size:15px;white-space:nowrap;transition:background .16s}
  .scanbox button:hover{background:var(--indigo-dark)}
  footer{background:var(--navy);color:#8d98ad;padding:40px 0;text-align:center;font-size:13px}
  footer a{color:#c3cad6;text-decoration:underline}
  .money{font-variant-numeric:tabular-nums}
  @media(max-width:900px){.hero{grid-template-columns:1fr;gap:40px}.grid4{grid-template-columns:1fr 1fr}.process-grid{grid-template-columns:1fr 1fr}.trust{grid-template-columns:1fr 1fr}}
  @media(max-width:600px){.grid4{grid-template-columns:1fr}.process-grid{grid-template-columns:1fr}.trust{grid-template-columns:1fr}.pricing-grid{grid-template-columns:1fr}.scanbox{flex-direction:column}.scanbox button{width:100%}.badge-hi{left:24px}}
</style>
</head>
<body id="top">

<nav class="wrap topnav">
  <div class="logo">SEO<span>Scan</span>.ai</div>
  <div class="nav-links">
    <a href="#methodology">{{NAV_METHOD}}</a>
    <a href="#reports">{{NAV_REPORTS}}</a>
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

<header class="wrap hero">
  <div>
    <span class="eyebrow">{{EYEBROW}}</span>
    <h1>{{H1_L1}} {{H1_EM}} {{H1_L3}}</h1>
    <p class="lead">{{SUB}}</p>
    <div class="hero-cta">
      <a class="btn btn-primary" href="#how" onclick="setTimeout(function(){var u=document.getElementById('url');if(u)u.focus()},60)">{{HERO_CTA_PRIMARY}}</a>
      <a class="btn btn-secondary" href="#reports">{{HERO_CTA_SECONDARY}}</a>
    </div>
    <p class="micro"><b>✓</b> {{MICRO1}} &nbsp;·&nbsp; <b>✓</b> {{MICRO2}} &nbsp;·&nbsp; <b>✓</b> {{MICRO3}}</p>
  </div>
  <div>
    <div class="preview">
      <div class="preview-head">
        <div style="text-align:left"><div class="lbl">{{PREV_LABEL}}</div><div class="pill">{{PREV_TITLE}}</div></div>
        <div style="text-align:right;font-size:12px;color:var(--muted)">seoscanaudit.com</div>
      </div>
      <div class="preview-body">
        <div class="pv-block"><h4>{{PREV_B1_T}}</h4>
          <div class="pv-row"><span class="chk">✓</span>{{PREV_B1_1}}</div>
          <div class="pv-row"><span class="chk">✓</span>{{PREV_B1_2}}</div></div>
        <div class="pv-block"><h4>{{PREV_B2_T}}</h4>
          <div class="pv-row"><span class="chk">✓</span>{{PREV_B2_1}} <span class="pv-badge p0">P0</span></div>
          <div class="pv-row"><span class="chk">✓</span>{{PREV_B2_2}}</div></div>
        <div class="pv-block"><h4>{{PREV_B3_T}}</h4>
          <div class="pv-row"><span class="chk">✓</span>{{PREV_B3_1}}</div>
          <div class="pv-row"><span class="chk">✓</span>{{PREV_B3_2}}</div></div>
      </div>
    </div>
  </div>
</header>

<section id="how">
  <div class="wrap">
    <div class="section-head">
      <span class="eyebrow">{{SCAN_EYEBROW}}</span>
      <h2>{{HOW_H2}}</h2>
      <p>{{HOW_SUB}}</p>
    </div>
    <div class="scanbox">
      <input id="url" type="url" placeholder="{{INPUT_PLACEHOLDER}}" required />
      <button onclick="runScan()">{{SCAN_BTN}}</button>
    </div>
    <div class="result" id="result">
      <h3>{{RESULT_TITLE}} <span id="rurl" style="color:var(--indigo)"></span></h3>
      <div class="demoNote" id="demoNote" style="display:none"></div>
      <div class="score">
        <div class="ring"><span id="rscore">—</span></div>
        <div style="font-size:13px;color:var(--muted);line-height:1.5">
          {{SCORE_LABEL}}<br /><b style="font-size:22px;color:var(--ink);display:block"><span id="rscoreBig">—</span> / 100</b>
          <span id="rscoreHint" style="color:var(--amber)">{{SCORE_HINT}}</span>
        </div>
      </div>
      <div class="toplist">
        <div class="row"><span class="lv {{TOP_LV}}">mid</span>{{TOP_PLACEHOLDER}}</div>
      </div>
      <div id="locked" style="margin-top:8px">
        <div class="lockrow"><span>🔒 {{LOCK_FIXLIST}}</span><b>{{LOCKED}}</b></div>
        <div class="lockrow"><span>🔒 {{LOCK_COMPETE}}</span><b>{{LOCKED}}</b></div>
        <div class="lockrow"><span>🔒 {{LOCK_AI_STEPS}}</span><b>{{LOCKED}}</b></div>
        <div style="margin:14px 0 4px;font-size:13px;color:var(--muted)">{{EMAIL_NOTE}}</div>
        <input id="email" type="email" placeholder="you@example.com" required
               style="width:100%;padding:12px 14px;font-size:15px;border:1px solid var(--line);border-radius:10px;outline:none;margin-bottom:10px" />
        <label style="display:flex;gap:8px;align-items:center;font-size:12px;color:var(--muted);margin-bottom:12px">
          <input id="consent" type="checkbox" required style="width:16px;height:16px;accent-color:var(--indigo)" />
          {{CONSENT}}
        </label>
        <button class="unlock" onclick="startCheckout()">{{UNLOCK_BTN}}</button>
        <div style="margin:10px 0 2px;font-size:12px;color:var(--teal);font-weight:600">{{GUARANTEE}}</div>
        <div style="font-size:11px;color:var(--muted)">{{AUTO_DELIVER}}</div>
      </div>
    </div>
    <p style="text-align:center;color:var(--muted);font-size:13px;margin-top:16px">{{TA}}</p>
  </div>
</section>

<section id="methodology" style="background:#fff">
  <div class="wrap">
    <div class="section-head">
      <span class="eyebrow">{{DIFF_EYEBROW}}</span>
      <h2>{{DIFF_H2}}</h2>
      <p>{{DIFF_SUB}}</p>
    </div>
    <div class="grid4">
      <div class="feat-card"><div class="tick">✓</div><h4>{{D1_T}}</h4><p>{{D1_D}}</p></div>
      <div class="feat-card"><div class="tick">✓</div><h4>{{D2_T}}</h4><p>{{D2_D}}</p></div>
      <div class="feat-card"><div class="tick">✓</div><h4>{{D3_T}}</h4><p>{{D3_D}}</p></div>
      <div class="feat-card"><div class="tick">✓</div><h4>{{D4_T}}</h4><p>{{D4_D}}</p></div>
    </div>
  </div>
</section>

<section class="process">
  <div class="wrap">
    <div class="section-head">
      <span class="eyebrow" style="color:#9eb0ff">{{PROC_EYEBROW}}</span>
      <h2>{{PROC_H2}}</h2>
      <p>{{PROC_SUB}}</p>
    </div>
    <div class="process-grid">
      <div class="step"><div class="num">{{PROC_1_N}}</div><h4>{{PROC_1_T}}</h4><p>{{PROC_1_D}}</p></div>
      <div class="step"><div class="num">{{PROC_2_N}}</div><h4>{{PROC_2_T}}</h4><p>{{PROC_2_D}}</p></div>
      <div class="step"><div class="num">{{PROC_3_N}}</div><h4>{{PROC_3_T}}</h4><p>{{PROC_3_D}}</p></div>
      <div class="step"><div class="num">{{PROC_4_N}}</div><h4>{{PROC_4_T}}</h4><p>{{PROC_4_D}}</p></div>
    </div>
  </div>
</section>

<section id="reports" style="background:#fff">
  <div class="wrap">
    <div class="section-head">
      <span class="eyebrow">{{PREVSEC_EYEBROW}}</span>
      <h2>{{PREVSEC_H2}}</h2>
      <p>{{PREVSEC_SUB}}</p>
    </div>
    <div style="max-width:880px;margin:0 auto">
      <div class="pv-block"><h4>{{PREV_B1_T}}</h4><div class="pv-row"><span class="chk">✓</span>{{PREV_B1_1}}</div></div>
      <div class="pv-block" style="margin-top:14px"><h4>{{PREV_B2_T}}</h4><div class="pv-row"><span class="chk">✓</span>{{PREV_B2_1}}</div></div>
      <div class="pv-block" style="margin-top:14px"><h4>{{PREV_B3_T}}</h4><div class="pv-row"><span class="chk">✓</span>{{PREV_B3_1}}</div></div>
      <div class="pv-block" style="margin-top:14px"><h4>{{PREV_B4_T}}</h4><div class="pv-row"><span class="chk">✓</span>{{PREV_B4_1}}</div></div>
    </div>
  </div>
</section>

<section id="pricing">
  <div class="wrap">
    <div class="section-head">
      <span class="eyebrow">{{PRICE_EYEBROW}}</span>
      <h2>{{PRICE_H2}}</h2>
      <p>{{PRICE_SUB}}</p>
    </div>
    <div class="pricing-grid">
      <div class="pcard">
        <h3 style="font-size:22px;font-weight:800">{{CARD1_TITLE}}</h3>
        <p class="who">{{CARD1_WHO}}</p>
        <div class="price money">US${{PRICE_USD}} <small>{{PRICE_UNIT}}</small></div>
        <ul>
          <li><span class="chk">✓</span>{{CARD1_1}}</li>
          <li><span class="chk">✓</span>{{CARD1_2}}</li>
          <li><span class="chk">✓</span>{{CARD1_3}}</li>
          <li><span class="chk">✓</span>{{CARD1_4}}</li>
          <li><span class="chk">✓</span>{{CARD1_5}}</li>
          <li><span class="chk">✓</span>{{CARD1_6}}</li>
        </ul>
        <div class="cta"><button class="btn btn-primary" style="width:100%" data-product="prod_seo_opportunity" onclick="chooseProduct(this)">{{CARD1_CTA}}</button></div>
      </div>
      <div class="pcard highlight">
        <span class="badge-hi">{{CARD2_BADGE}}</span>
        <h3 style="font-size:22px;font-weight:800">{{CARD2_TITLE}}</h3>
        <p class="who">{{CARD2_WHO}}</p>
        <div class="price money">US${{GROWTH_PRICE_USD}} <small>{{PRICE_UNIT}}</small></div>
        <ul>
          <li><span class="chk">✓</span>{{CARD2_1}}</li>
          <li><span class="chk">✓</span>{{CARD2_2}}</li>
          <li><span class="chk">✓</span>{{CARD2_3}}</li>
          <li><span class="chk">✓</span>{{CARD2_4}}</li>
          <li><span class="chk">✓</span>{{CARD2_5}}</li>
          <li><span class="chk">✓</span>{{CARD2_6}}</li>
        </ul>
        <div class="cta"><button class="btn btn-primary" style="width:100%" data-product="prod_seo_growth" onclick="chooseProduct(this)">{{CARD2_CTA}}</button></div>
      </div>
    </div>
    <p style="text-align:center;color:var(--muted);font-size:13px;margin-top:26px">{{PRICE_FOOT}}</p>
  </div>
</section>

<section style="background:#fff;padding:48px 0">
  <div class="wrap">
    <div class="trust">
      <div class="trust-item"><b>{{T1_T}}</b><span>{{T1_D}}</span></div>
      <div class="trust-item"><b>{{T2_T}}</b><span>{{T2_D}}</span></div>
      <div class="trust-item"><b>{{T3_T}}</b><span>{{T3_D}}</span></div>
      <div class="trust-item"><b>{{T4_T}}</b><span>{{T4_D}}</span></div>
    </div>
  </div>
</section>

<section class="final-cta">
  <div class="wrap">
    <span class="eyebrow" style="color:#9eb0ff">{{CTA_EYEBROW}}</span>
    <h2>{{CTA_H2}}</h2>
    <a class="btn btn-primary" href="#reports">{{CTA_BTN}}</a>
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
  var CURRENT_LANG = 'en';
  function setLang(){ try{ var seg=window.location.pathname.split('/')[1]; if(seg&&['en','zh-Hant','zh-Hans','ja','es'].indexOf(seg)!==-1) CURRENT_LANG=seg; }catch(e){} }
  function chooseProduct(btn){ var pid=btn.getAttribute('data-product'); try{ window.__selectedProduct=pid; }catch(e){} var t=document.getElementById('how'); if(t) t.scrollIntoView({behavior:'smooth',block:'start'}); setTimeout(function(){ var u=document.getElementById('url'); if(u) u.focus(); },60); }
  function runScan(){
    var u = document.getElementById('url').value.trim();
    if(!u){ document.getElementById('url').focus(); return; }
    document.getElementById('rscore').textContent = '…';
    document.getElementById('demoNote').style.display = 'none';
    document.getElementById('result').style.display = 'block';
    document.getElementById('result').scrollIntoView({behavior:'smooth', block:'center'});
    fetch('/api/scan', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url: u})})
      .then(function(r){ return r.json(); })
      .then(function(data){
        if (data.error){ document.getElementById('rscore').textContent = '—'; document.getElementById('demoNote').style.display = 'block'; document.getElementById('demoNote').textContent = '{{SCAN_ERR}} ' + data.error; return; }
        var clean = u.replace(/^https?:\\/\\//,'').replace(/\\/$/,'');
        var scVal = (data.score != null) ? data.score : '—';
        document.getElementById('rscore').textContent = scVal;
        var big = document.getElementById('rscoreBig'); if(big) big.textContent = scVal;
        var hint = document.getElementById('rscoreHint');
        if(hint) hint.textContent = (data.score != null) ? ((data.score >= 80 ? '{{HINT_GOOD}}' : (data.score >= 50 ? '{{HINT_MID}}' : '{{HINT_BAD}}'))) : '{{HINT_NODIAG}}';
        document.getElementById('rurl').textContent = clean;
        var fc = (data.fix_count != null) ? data.fix_count : (data.fix_list || []).length;
        document.querySelectorAll('.fixCount').forEach(function(el){ el.textContent = fc; });
        var top = (data.top_issues || []).slice(0,5);
        var list = document.getElementById('toplistResult');
        if(!list){ list = document.createElement('div'); list.id='toplistResult'; document.querySelector('.toplist').appendChild(list); }
        list.innerHTML = '';
        if(top.length === 0){ top = [{priority:'low', issue:'{{TOP_EMPTY}}'}]; }
        top.forEach(function(t){ var lv = t.priority === 'urgent' ? 'hi' : (t.priority === 'high' ? 'hi' : 'md'); var row = document.createElement('div'); row.className='row'; row.innerHTML='<span class="lv '+lv+'">'+t.priority+'</span>'+t.issue; list.appendChild(row); });
        var toplist = document.querySelector('.toplist');
        Array.prototype.slice.call(toplist.children).forEach(function(c){ if(c.className && String(c.className).indexOf('row') !== -1 && !c.id){ toplist.removeChild(c); } });
        if(typeof window.__scanTotal === 'number'){ window.__scanTotal += 1; var sc = document.getElementById('scanCount'); if(sc) sc.textContent = window.__scanTotal; }
      })
      .catch(function(e){ document.getElementById('rscore').textContent = '—'; document.getElementById('demoNote').style.display = 'block'; document.getElementById('demoNote').textContent = '{{CONNECT_ERR}} ' + e; });
  }
  function startCheckout(){
    var u = document.getElementById('url').value.trim();
    var em = document.getElementById('email') ? document.getElementById('email').value.trim() : '';
    var note = document.getElementById('demoNote');
    function showNote(msg){ note.style.display='block'; note.textContent = msg; }
    var productId = (window.__selectedProduct || 'prod_seo_opportunity');
    var sel = document.getElementById('langSel');
    var langOpt = sel ? sel.value.replace(/^\\//,'') : '';
    var reportLanguage = (langOpt && ['en','zh-Hant','zh-Hans','ja','es'].indexOf(langOpt)!==-1) ? langOpt : 'en';
    if(!em){ showNote('{{EMAIL_REQ}}'); document.getElementById('email').focus(); return; }
    var orderPayload = { url:u, customer_email:em, selected_product_id:productId, report_language:reportLanguage };
    fetch('/api/order', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(orderPayload)})
      .then(function(r){ return r.json().then(function(d){ return {ok:r.ok, json:d}; }); })
      .then(function(res){
        var d = res.json;
        if(!res.ok || d.error){ showNote('{{ORDER_ERR}} ' + (d.error || '{{UNKNOWN_ERR}}')); return; }
        var orderId = d.order_id;
        var checkoutPayload = { url:u, order_id:orderId, customer_email:em, selected_product_id:productId, report_language:reportLanguage };
        fetch('/api/create-checkout', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(checkoutPayload)})
          .then(function(r){ return r.json(); })
          .then(function(cd){
            if(cd.redirect_url){ window.location.href = cd.redirect_url; return; }
            showNote('{{CHECKOUT_PRE}} ' + orderId + ' {{CHECKOUT_POST}}');
            document.getElementById('result').scrollIntoView({behavior:'smooth', block:'center'});
          })
          .catch(function(e){ showNote('{{CONNECT_CHECKOUT}} ' + e); });
      })
      .catch(function(e){ showNote('{{CONNECT_ORDER}} ' + e); });
  }
  window.__scanTotal = 0;
  setLang();
  document.addEventListener('keydown', function(e){ if(e.key==='Enter' && document.activeElement.id==='url') runScan(); });
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Per-language copy. Prices/locked/scan-wiring 由 token 填（config 單一來源）。
# ---------------------------------------------------------------------------
def base(lang_attrib):
    return {
        "HTML_LANG": lang_attrib,
        "SEL_EN": "", "SEL_ZHH": "", "SEL_ZHS": "", "SEL_JA": "", "SEL_ES": "",
    }

EN = dict(base("en"), SEL_EN="selected", **{
    "TITLE": "Know What to Fix on Your Website — Evidence-Led SEO Decision Report",
    "META_DESC": "Get a decision-ready SEO report: your highest-priority opportunities, why they matter to your business, and a practical 90-day action plan. Professional PDF delivery in your chosen language.",
    "NAV_METHOD": "Methodology", "NAV_REPORTS": "Reports", "NAV_PRICE": "Pricing",
    "EYEBROW": "Evidence-led SEO research",
    "H1_L1": "Know what to fix on your website —", "H1_EM": "before you waste another month on SEO.", "H1_L3": "",
    "SUB": "Get a decision-ready SEO report that identifies your highest-priority opportunities, explains why they matter to your business, and gives you a practical 90-day action plan.",
    "HERO_CTA_PRIMARY": "Scan my site free", "HERO_CTA_SECONDARY": "See what’s included",
    "MICRO1": "Choose your output language before payment", "MICRO2": "Professional PDF delivery", "MICRO3": "No login required",
    "PREV_LABEL": "Illustrative report preview", "PREV_TITLE": "SEO Opportunity Diagnostic",
    "PREV_B1_T": "Executive decision summary", "PREV_B1_1": "Score 64/100 — Needs work", "PREV_B1_2": "3 findings, est. +9 pts available",
    "PREV_B2_T": "Evidence-led finding", "PREV_B2_1": "Speed is your biggest drag", "PREV_B2_2": "TTFB measured 1240 ms, no gzip",
    "PREV_B3_T": "Prioritised action ledger · 90-day roadmap", "PREV_B3_1": "Owner · Effort · Acceptance criteria", "PREV_B3_2": "Days 0–30 · 31–60 · 61–90",
    "SCAN_EYEBROW": "Start with a free scan",
    "HOW_H2": "See your real issues first — before you pay for anything",
    "HOW_SUB": "No signup, no credit card. Paste your website URL and get your SEO health score and top issues in seconds.",
    "INPUT_PLACEHOLDER": "Paste your website URL, e.g. mybusiness.com",
    "SCAN_BTN": "Scan My Site Free",
    "RESULT_TITLE": "Scan result:",
    "SCORE_LABEL": "SEO health score", "SCORE_HINT": "Scanning…",
    "TOP_LV": "md", "TOP_PLACEHOLDER": "Enter your URL and click “Scan My Site Free” to see real data on your Top issues",
    "LOCK_FIXLIST": "Full <span class='fixCount'>—</span>-item fix list (updates after scan)",
    "LOCKED": "Locked", "LOCK_COMPETE": "Competitor comparison analysis", "LOCK_AI_STEPS": "AI step-by-step fix guide + prioritization",
    "EMAIL_NOTE": "Receive the report by email (full PDF delivery):",
    "CONSENT": "I agree my email is used only to deliver this report, as described in the Privacy Policy. I understand I can opt out anytime.",
    "UNLOCK_BTN": "Unlock Full Report",
    "GUARANTEE": "7-day peace-of-mind guarantee: full refund before delivery · free re-review after",
    "AUTO_DELIVER": "Auto-delivered to your email within ~10 minutes of payment",
    "TA": "Free · no signup · instant result",
    "DIFF_EYEBROW": "Why this is different", "DIFF_H2": "Not another SEO error export.", "DIFF_SUB": "Evidence-led research, prioritised for your business.",
    "D1_T": "Less noise", "D1_D": "Material risks and opportunities — not a huge generic error list.",
    "D2_T": "Clear evidence", "D2_D": "Facts, evidence-based inferences and validation items are kept distinct.",
    "D3_T": "Usable work", "D3_D": "Actions have owner, effort, dependency, acceptance criteria and validation.",
    "D4_T": "Business-first", "D4_D": "Recommendations relate to business pages, customer journeys and commercial intent.",
    "PROC_EYEBROW": "The research process", "PROC_H2": "How each report is built", "PROC_SUB": "A disciplined, reproducible method — not an automated guess.",
    "PROC_1_N": "STEP 1", "PROC_1_T": "Study your website", "PROC_1_D": "Read structure, navigation, key commercial and content pages.",
    "PROC_2_N": "STEP 2", "PROC_2_T": "Research search patterns", "PROC_2_D": "Observe what actually ranks for your commercial intents.",
    "PROC_3_N": "STEP 3", "PROC_3_T": "Build the evidence", "PROC_3_D": "Each finding ties to a verifiable observation with source.",
    "PROC_4_N": "STEP 4", "PROC_4_T": "Prioritise the work", "PROC_4_D": "Rank by business impact, effort and confidence.",
    "PREVSEC_EYEBROW": "Illustrative report preview", "PREVSEC_H2": "What a decision-ready SEO report looks like", "PREVSEC_SUB": "Liberally labelled samples — your real report is personalised to your website.",
    "PREV_B4_T": "90-day roadmap", "PREV_B4_1": "Days 0–30 · 31–60 · 61–90, with owners",
    "PRICE_EYEBROW": "Choose your report", "PRICE_H2": "Two evidence-led reports. One clear path.", "PRICE_SUB": "Choose a report, choose your language, pay securely. Your PDF is delivered to your email.",
    "PRICE_UNIT": "/ once",
    "CARD1_TITLE": "SEO Opportunity Diagnostic", "CARD1_WHO": "For business owners who need to know which SEO work deserves attention over the next 90 days.",
    "CARD1_1": "Evidence-led website and search review", "CARD1_2": "3–5 priority findings", "CARD1_3": "Top-five action plan", "CARD1_4": "Business-readable executive summary", "CARD1_5": "90-day roadmap", "CARD1_6": "Public-data validation checklist", "CARD1_CTA": "Choose Report",
    "CARD2_BADGE": "Best for teams ready to execute", "CARD2_TITLE": "SEO Growth Blueprint", "CARD2_WHO": "For teams that need a more complete action system for content, marketing and development.",
    "CARD2_1": "Deeper strategy and architecture assessment", "CARD2_2": "Topic, intent and page-purpose map", "CARD2_3": "Detailed prioritised action ledger", "CARD2_4": "Content opportunity briefs", "CARD2_5": "Developer-ready implementation briefs", "CARD2_6": "90-day roadmap with owners and validation plan", "CARD2_CTA": "Choose Report",
    "PRICE_FOOT": "Both reports delivered as a professional PDF in your chosen language.",
    "T1_T": "Evidence before opinion", "T1_D": "Findings rest on observable facts, not guesses.",
    "T2_T": "Facts vs assumptions", "T2_D": "Fact, inference and hypothesis are labelled.",
    "T3_T": "Clear boundaries", "T3_D": "What we can and can’t verify is stated honestly.",
    "T4_T": "Actionable by design", "T4_D": "Owner, effort and how to check success included.",
    "CTA_EYEBROW": "A cleaner way forward", "CTA_H2": "Stop collecting SEO tasks. Start making SEO decisions.", "CTA_BTN": "Choose your report",
    "FOOT1": "SEO Scan.ai — evidence-led AI SEO audit report",
    "FOOT_PRIVACY": "Privacy Policy", "FOOT_TERMS": "Terms of Service", "FOOT_REFUND": "Refund Policy", "FOOT_DISCLAIMER": "Disclaimer",
    "COPYRIGHT": "© 2026 SEO Scan.ai",
    "SCAN_ERR": "Scan error:", "HINT_GOOD": "✅ Healthy site", "HINT_MID": "⚠️ Worth improving", "HINT_BAD": "🔴 Many issues", "HINT_NODIAG": "Could not read diagnosis",
    "TOP_EMPTY": "No obvious technical errors detected",
    "CONNECT_ERR": "Could not reach scan backend:", "EMAIL_REQ": "Please enter the email to receive the report (full PDF goes here)",
    "ORDER_ERR": "Order failed:", "UNKNOWN_ERR": "unknown error",
    "CHECKOUT_PRE": "Order created (", "CHECKOUT_POST": "). Redirecting to secure payment…",
    "CONNECT_CHECKOUT": "Could not reach checkout server:", "CONNECT_ORDER": "Could not reach order server:",
})

# 《共享翻譯》 —— 其餘 4 語言（用張 dict 覆蓋 EN 值；未覆蓋 key 沿用 EN 有風險，故全部 key 都要提供）
ZH_HANT = dict(base("zh-Hant"),
    **{k: EN[k] for k in EN if k in ("SEL_EN", "SEL_ZHS", "SEL_JA", "SEL_ES")},
    **{
    "SEL_ZHH": "selected",
    "TITLE": "知道網站要修啲咩 — 證據為本嘅 SEO 決策報告",
    "META_DESC": "攞一份決策就緒嘅 SEO 報告：你最高優先嘅機會、點解對你生意重要、仲有實用嘅 90 日行動計劃。以你揀嘅語言交付專業 PDF。",
    "NAV_METHOD": "方法論", "NAV_REPORTS": "報告", "NAV_PRICE": "定價",
    "EYEBROW": "證據為本嘅 SEO 研究",
    "H1_L1": "知道網站要修啲咩 —", "H1_EM": "唔好再浪費多一個月喺 SEO。", "H1_L3": "",
    "SUB": "攞一份決策就緒嘅 SEO 報告，識別你最高優先嘅機會、解釋點解對你生意重要，並提供實用嘅 90 日行動計劃。",
    "HERO_CTA_PRIMARY": "免費 Scan 我網站", "HERO_CTA_SECONDARY": "睇下包括啲咩",
    "MICRO1": "付款前揀定輸出語言", "MICRO2": "專業 PDF 交付", "MICRO3": "唔使登入",
    "PREV_LABEL": "示意報告預覽", "PREV_TITLE": "SEO 機會診斷",
    "PREV_B1_T": "執行決策摘要", "PREV_B1_1": "得分 64/100 — 有待改善", "PREV_B1_2": "3 項發現，預期 +9 分",
    "PREV_B2_T": "證據為本嘅發現", "PREV_B2_1": "速度係你最大樽頸", "PREV_B2_2": "實測 TTFB 1240ms，冇 gzip",
    "PREV_B3_T": "優先行動清單 · 90 日路線圖", "PREV_B3_1": "負責人 · 工作量 · 驗收準則", "PREV_B3_2": "第 0–30 · 31–60 · 61–90 日",
    "SCAN_EYEBROW": "由免費 scan 開始",
    "HOW_H2": "先睇你嘅真問題 — 唔好未買就俾錢",
    "HOW_SUB": "唔使註冊、唔使信用卡。貼你網站 URL，幾秒攞到 SEO 健康分同最嚴重問題。",
    "INPUT_PLACEHOLDER": "貼你網站 URL，例如 mybusiness.com",
    "SCAN_BTN": "免費 Scan 我網站",
    "RESULT_TITLE": "Scan 結果：",
    "SCORE_LABEL": "SEO 健康分", "SCORE_HINT": "掃描中…",
    "TOP_LV": "md", "TOP_PLACEHOLDER": "貼你 URL 再撳「免費 Scan」，睇到你網站 Top 問題嘅真實數據",
    "LOCK_FIXLIST": "完整 <span class='fixCount'>—</span> 項修復清單（scan 後更新）",
    "LOCKED": "鎖住", "LOCK_COMPETE": "競爭對手對比分析", "LOCK_AI_STEPS": "AI 逐步修復指引 + 優先次序",
    "EMAIL_NOTE": "收報告 email（交付完整 PDF）：",
    "CONSENT": "我同意將 email 僅用於交付本報告（見私隱政策），可隨時取消訂閱。",
    "UNLOCK_BTN": "解鎖完整報告",
    "GUARANTEE": "7 日放心保證：交付前全額退 · 交付後免費重審",
    "AUTO_DELIVER": "付款後約 10 分鐘自動送到你 email",
    "TA": "免費 · 唔使註冊 · 即時結果",
    "DIFF_EYEBROW": "點解唔同", "DIFF_H2": "唔係另一份 SEO 錯誤清單。", "DIFF_SUB": "證據為本嘅研究，按你生意優先排列。",
    "D1_T": "少啲噪音", "D1_D": "實質風險同機會 — 唔係一大疊通用錯誤清單。",
    "D2_T": "清晰證據", "D2_D": "事實、基於證據嘅推論同驗證項目會清楚分開。",
    "D3_T": "實用嘅工作", "D3_D": "行動有負責人、工作量、依賴、驗收準則同驗證方法。",
    "D4_T": "生意優先", "D4_D": "建議關乎生意頁面、客戶旅程同商業意圖。",
    "PROC_EYEBROW": "研究流程", "PROC_H2": "每份報告點樣整出嚟", "PROC_SUB": "一套嚴謹、可重現嘅方法 — 唔係自動估。",
    "PROC_1_N": "第 1 步", "PROC_1_T": "研究你嘅網站", "PROC_1_D": "睇結構、導覽、關鍵商業同內容頁。",
    "PROC_2_N": "第 2 步", "PROC_2_T": "研究搜尋模式", "PROC_2_D": "觀察你商業意圖實際排到啲咩。",
    "PROC_3_N": "第 3 步", "PROC_3_T": "建立證據", "PROC_3_D": "每個發現都連繫到可驗證、有出處嘅觀察。",
    "PROC_4_N": "第 4 步", "PROC_4_T": "排列優先次序", "PROC_4_D": "按商業影響、工作量同信心度排序。",
    "PREVSEC_EYEBROW": "示意報告預覽", "PREVSEC_H2": "一份決策就緒嘅 SEO 報告係點樣", "PREVSEC_SUB": "已清楚標示樣本 — 你真實報告會按你網站個人化。",
    "PREV_B4_T": "90 日路線圖", "PREV_B4_1": "第 0–30 · 31–60 · 61–90 日，附負責人",
    "PRICE_EYEBROW": "揀你嘅報告", "PRICE_H2": "兩份證據為本嘅報告。一條清晰路。", "PRICE_SUB": "揀報告、揀語言、安全付款。PDF 送到你 email。",
    "PRICE_UNIT": "/ 一次",
    "CARD1_TITLE": "SEO 機會診斷", "CARD1_WHO": "俾要知未來 90 日邊啲 SEO 工作值得關注嘅生意東主。",
    "CARD1_1": "證據為本嘅網站同搜尋審查", "CARD1_2": "3–5 項優先發現", "CARD1_3": "Top 5 行動計劃", "CARD1_4": "生意人睇得明嘅執行摘要", "CARD1_5": "90 日路線圖", "CARD1_6": "公開數據驗證清單", "CARD1_CTA": "揀呢份報告",
    "CARD2_BADGE": "最啱準備好執行嘅團隊", "CARD2_TITLE": "SEO 增長藍圖", "CARD2_WHO": "俾需要更完整行動系統（內容、市場、開發）嘅團隊。",
    "CARD2_1": "更深嘅策略同架構評估", "CARD2_2": "話題、意圖同頁面用途地圖", "CARD2_3": "詳細優先行動清單", "CARD2_4": "內容機會簡報", "CARD2_5": "開發就緒嘅實作簡報", "CARD2_6": "附負責人同驗證計劃嘅 90 日路線圖", "CARD2_CTA": "揀呢份報告",
    "PRICE_FOOT": "兩份報告都係以你揀嘅語言交付專業 PDF。",
    "T1_T": "證據先於意見", "T1_D": "發現建基於可觀察事實，唔靠估。",
    "T2_T": "事實 vs 假設", "T2_D": "事實、推論同假設會清楚標明。",
    "T3_T": "清楚界線", "T3_D": "我哋做到同做唔到驗證嘅嘢會誠實講明。",
    "T4_T": "設計上可執行", "T4_D": "包括負責人、工作量同點樣 check 成功。",
    "CTA_EYEBROW": "更清晰嘅前行路", "CTA_H2": "停止收集 SEO 任務。開始做 SEO 決定。", "CTA_BTN": "揀你嘅報告",
    "FOOT1": "SEO Scan.ai — 證據為本嘅 AI SEO 審計報告",
    "FOOT_PRIVACY": "私隱政策", "FOOT_TERMS": "服務條款", "FOOT_REFUND": "退款政策", "FOOT_DISCLAIMER": "免責聲明",
    "COPYRIGHT": "© 2026 SEO Scan.ai",
    "SCAN_ERR": "Scan 錯誤：", "HINT_GOOD": "✅ 網站健康", "HINT_MID": "⚠️ 值得改善", "HINT_BAD": "🔴 好多問題", "HINT_NODIAG": "無法讀取診斷",
    "TOP_EMPTY": "未偵測到明顯技術錯誤",
    "CONNECT_ERR": "連唔到 scan 後端：", "EMAIL_REQ": "請輸入收報告嘅 email（完整 PDF 會送到呢度）",
    "ORDER_ERR": "落單失敗：", "UNKNOWN_ERR": "未知錯誤",
    "CHECKOUT_PRE": "訂單已建立（", "CHECKOUT_POST": "）。跳去安全付款…",
    "CONNECT_CHECKOUT": "連唔到 checkout server：", "CONNECT_ORDER": "連唔到 order server：",
})

ZH_HANS = dict(base("zh-Hans"), SEL_ZHS="selected", **{
    "TITLE": "知道网站要修什么 — 基于证据的 SEO 决策报告",
    "META_DESC": "获取一份决策就绪的 SEO 报告：你的最高优先机会、为何对你的业务重要，以及实用的 90 天行动计划。以你选择的语言交付专业 PDF。",
    "NAV_METHOD": "方法论", "NAV_REPORTS": "报告", "NAV_PRICE": "定价",
    "EYEBROW": "基于证据的 SEO 研究",
    "H1_L1": "知道网站要修什么 —", "H1_EM": "在 SEO 上再浪费一个月之前。", "H1_L3": "",
    "SUB": "获取一份决策就绪的 SEO 报告，识别你的最高优先机会，解释为何对你的业务重要，并提供实用的 90 天行动计划。",
    "HERO_CTA_PRIMARY": "免费扫描我的网站", "HERO_CTA_SECONDARY": "查看包含内容",
    "MICRO1": "付款前选择输出语言", "MICRO2": "专业 PDF 交付", "MICRO3": "无需登录",
    "PREV_LABEL": "示意报告预览", "PREV_TITLE": "SEO 机会诊断",
    "PREV_B1_T": "执行决策摘要", "PREV_B1_1": "得分 64/100 — 有待改善", "PREV_B1_2": "3 项发现，预期 +9 分",
    "PREV_B2_T": "基于证据的发现", "PREV_B2_1": "速度是最大瓶颈", "PREV_B2_2": "实测 TTFB 1240ms，无 gzip",
    "PREV_B3_T": "优先行动清单 · 90 天路线图", "PREV_B3_1": "负责人 · 工作量 · 验收标准", "PREV_B3_2": "第 0–30 · 31–60 · 61–90 天",
    "SCAN_EYEBROW": "从免费扫描开始",
    "HOW_H2": "先看真实问题 — 付款前先确认",
    "HOW_SUB": "无需注册、无需信用卡。粘贴网站 URL，几秒获得 SEO 健康分和最重要的问题。",
    "INPUT_PLACEHOLDER": "粘贴你的网站 URL，例如 mybusiness.com",
    "SCAN_BTN": "免费扫描我的网站",
    "RESULT_TITLE": "扫描结果：",
    "SCORE_LABEL": "SEO 健康分", "SCORE_HINT": "扫描中…",
    "TOP_LV": "md", "TOP_PLACEHOLDER": "粘贴你的 URL 并点击「免费扫描」，查看你网站 Top 问题的真实数据",
    "LOCK_FIXLIST": "完整 <span class='fixCount'>—</span> 项修复清单（扫描后更新）",
    "LOCKED": "已锁定", "LOCK_COMPETE": "竞争对手对比分析", "LOCK_AI_STEPS": "AI 逐步修复指引 + 优先级",
    "EMAIL_NOTE": "通过 email 接收报告（交付完整 PDF）：",
    "CONSENT": "我同意将 email 仅用于交付本报告（见隐私政策），可随时取消订阅。",
    "UNLOCK_BTN": "解锁完整报告",
    "GUARANTEE": "7 天安心保证：交付前全额退款 · 交付后免费复审",
    "AUTO_DELIVER": "付款后约 10 分钟自动送到你的 email",
    "TA": "免费 · 无需注册 · 即时结果",
    "DIFF_EYEBROW": "为何不同", "DIFF_H2": "不是又一份 SEO 错误清单。", "DIFF_SUB": "基于证据的研究，按你的业务排序。",
    "D1_T": "更少噪音", "D1_D": "实质性风险与机会 — 不是一堆通用错误清单。",
    "D2_T": "清晰证据", "D2_D": "事实、基于证据的推断与需验证项目会清楚区分。",
    "D3_T": "可用的工作", "D3_D": "行动有负责人、工作量、依赖、验收标准和验证方法。",
    "D4_T": "业务优先", "D4_D": "建议关联业务页面、客户旅程和商业意图。",
    "PROC_EYEBROW": "研究流程", "PROC_H2": "每份报告如何构建", "PROC_SUB": "一套严谨、可复现的方法 — 不是自动猜测。",
    "PROC_1_N": "第 1 步", "PROC_1_T": "研究你的网站", "PROC_1_D": "查看结构、导航、关键商业和内容页面。",
    "PROC_2_N": "第 2 步", "PROC_2_T": "研究搜索模式", "PROC_2_D": "观察你的商业意图实际排名什么。",
    "PROC_3_N": "第 3 步", "PROC_3_T": "建立证据", "PROC_3_D": "每个发现都关联到可验证的观测与来源。",
    "PROC_4_N": "第 4 步", "PROC_4_T": "排列优先级", "PROC_4_D": "按商业影响、工作量和信心度排序。",
    "PREVSEC_EYEBROW": "示意报告预览", "PREVSEC_H2": "一份决策就绪的 SEO 报告长什么样", "PREVSEC_SUB": "已明确标示样本 — 你的真实报告会按你的网站个性化。",
    "PREV_B4_T": "90 天路线图", "PREV_B4_1": "第 0–30 · 31–60 · 61–90 天，附负责人",
    "PRICE_EYEBROW": "选择你的报告", "PRICE_H2": "两份基于证据的报告。一条清晰路径。", "PRICE_SUB": "选择报告、选择语言、安全付款。PDF 送到你的 email。",
    "PRICE_UNIT": "/ 一次",
    "CARD1_TITLE": "SEO 机会诊断", "CARD1_WHO": "适合需要知道未来 90 天哪些 SEO 工作值得关注的企业主。",
    "CARD1_1": "基于证据的网站与搜索审查", "CARD1_2": "3–5 项优先发现", "CARD1_3": "Top 5 行动计划", "CARD1_4": "商家能读懂的执行摘要", "CARD1_5": "90 天路线图", "CARD1_6": "公开数据验证清单", "CARD1_CTA": "选择这份报告",
    "CARD2_BADGE": "最适合准备执行的团队", "CARD2_TITLE": "SEO 增长蓝图", "CARD2_WHO": "适合需要更完整行动系统（内容、营销、开发）的团队。",
    "CARD2_1": "更深入的策略与架构评估", "CARD2_2": "话题、意图与页面用途地图", "CARD2_3": "详细的优先行动清单", "CARD2_4": "内容机会简报", "CARD2_5": "开发者就绪的实施简报", "CARD2_6": "附负责人与验证计划的90天路线图", "CARD2_CTA": "选择这份报告",
    "PRICE_FOOT": "两份报告均以你选择的语言交付专业 PDF。",
    "T1_T": "证据先于意见", "T1_D": "发现基于可观察的事实，而非猜测。",
    "T2_T": "事实 vs 假设", "T2_D": "事实、推断与假设会明确标注。",
    "T3_T": "明确边界", "T3_D": "我们能验证和不能验证的东西会诚实说明。",
    "T4_T": "设计上可执行", "T4_D": "包括负责人、工作量和如何检查成功。",
    "CTA_EYEBROW": "更清晰的前行之路", "CTA_H2": "停止收集 SEO 任务。开始做 SEO 决策。", "CTA_BTN": "选择你的报告",
    "FOOT1": "SEO Scan.ai — 基于证据的 AI SEO 审计报告",
    "FOOT_PRIVACY": "隐私政策", "FOOT_TERMS": "服务条款", "FOOT_REFUND": "退款政策", "FOOT_DISCLAIMER": "免责声明",
    "COPYRIGHT": "© 2026 SEO Scan.ai",
    "SCAN_ERR": "扫描错误：", "HINT_GOOD": "✅ 网站健康", "HINT_MID": "⚠️ 值得改善", "HINT_BAD": "🔴 很多问题", "HINT_NODIAG": "无法读取诊断",
    "TOP_EMPTY": "未检测到明显技术错误",
    "CONNECT_ERR": "无法连接扫描后端：", "EMAIL_REQ": "请输入接收报告用的 email（完整 PDF 会送到这里）",
    "ORDER_ERR": "下单失败：", "UNKNOWN_ERR": "未知错误",
    "CHECKOUT_PRE": "订单已创建（", "CHECKOUT_POST": "）。正在跳转安全付款…",
    "CONNECT_CHECKOUT": "无法连接 checkout 服务器：", "CONNECT_ORDER": "无法连接订单服务器：",
})

JA = dict(base("ja"), SEL_JA="selected", **{
    "TITLE": "Webサイトで直すべきことが分かる — エビデンス主導のSEO意思決定レポート",
    "META_DESC": "最重要の機会、それがビジネスに重要な理由、実践的な90日行動計画を示す、意思決定に使えるSEOレポート。選択した言語でプロ品質のPDFをお届け。",
    "NAV_METHOD": "手法", "NAV_REPORTS": "レポート", "NAV_PRICE": "料金",
    "EYEBROW": "エビデンス主導のSEO調査",
    "H1_L1": "Webサイトで直すべきことが分かる —", "H1_EM": "SEOにまた一ヶ月無駄にする前に。", "H1_L3": "",
    "SUB": "最重要の機会を特定し、それがビジネスに重要な理由を説明し、実践的な90日行動計画を提供する、意思決定に使えるSEOレポートを入手。",
    "HERO_CTA_PRIMARY": "無料でスキャン", "HERO_CTA_SECONDARY": "内容を見る",
    "MICRO1": "支払い前に出力言語を選択", "MICRO2": "プロ品質のPDF納品", "MICRO3": "ログイン不要",
    "PREV_LABEL": "サンプル(レポート予告)", "PREV_TITLE": "SEO機会診断",
    "PREV_B1_T": "経営判断サマリー", "PREV_B1_1": "スコア64/100 — 改善が必要", "PREV_B1_2": "3件の所見、予想+9pt",
    "PREV_B2_T": "エビデンス主導の所見", "PREV_B2_1": "速度が最大のボトルネック", "PREV_B2_2": "実測TTFB 1240ms、gzipなし",
    "PREV_B3_T": "優先アクション台帳 · 90日ロードマップ", "PREV_B3_1": "担当者 · 工数 · 受入基準", "PREV_B3_2": "0–30 · 31–60 · 61–90日目",
    "SCAN_EYEBROW": "無料スキャンから開始",
    "HOW_H2": "支払う前に、まず実際の問題を見る",
    "HOW_SUB": "登録不要・カード不要。サイトURLを貼るだけで、SEO健全性スコアと最重要問題を数秒で取得。",
    "INPUT_PLACEHOLDER": "サイトURLを貼る(例: mybusiness.com)",
    "SCAN_BTN": "無料でスキャン",
    "RESULT_TITLE": "スキャン結果：",
    "SCORE_LABEL": "SEO健全性スコア", "SCORE_HINT": "スキャン中…",
    "TOP_LV": "md", "TOP_PLACEHOLDER": "URLを貼って「無料でスキャン」すると、サイトのTop問題の実データが表示",
    "LOCK_FIXLIST": "完全な<span class='fixCount'>—</span>件の修正リスト(スキャン後に更新)",
    "LOCKED": "ロック中", "LOCK_COMPETE": "競合比較分析", "LOCK_AI_STEPS": "AI段階別修正ガイド＋優先度",
    "EMAIL_NOTE": "レポートをemailで受け取る(完全版PDFを納品)：",
    "CONSENT": "本報告書の配信のためだけにメールを使用することに同意します（プライバシーポリシー参照）。いつでも登録解除できます。",
    "UNLOCK_BTN": "完全レポートを解除",
    "GUARANTEE": "7日間の安心保証：納品前に全額返金 · 納品後に無料で再審査",
    "AUTO_DELIVER": "お支払い後およそ10分でメールにお届け",
    "TA": "無料 · 登録不要 · 即時結果",
    "DIFF_EYEBROW": "何が違うか", "DIFF_H2": "また別のSEOエラー一覧ではない。", "DIFF_SUB": "エビデンス主導の調査を、あなたのビジネス優先で順位付け。",
    "D1_T": "ノイズを削減", "D1_D": "実質的なリスクと機会 — 大量の汎用エラー一覧ではありません。",
    "D2_T": "明確な根拠", "D2_D": "事実、根拠に基づく推論、検証項目を明確に区別。",
    "D3_T": "使える仕事", "D3_D": "アクションには担当者・工数・依存・受入基準・検証方法を記載。",
    "D4_T": "ビジネス優先", "D4_D": "推奨はビジネスページ、顧客経路、商取的意図に関連付け。",
    "PROC_EYEBROW": "調査プロセス", "PROC_H2": "各レポートの作り方", "PROC_SUB": "規律ある再現可能な方法 — 自動推測ではありません。",
    "PROC_1_N": "STEP 1", "PROC_1_T": "サイトを調査", "PROC_1_D": "構造、ナビ、主要な営業・コンテンツページを確認。",
    "PROC_2_N": "STEP 2", "PROC_2_T": "検索パターンを調査", "PROC_2_D": "商談意図で実際に何が上位表示されるか観察。",
    "PROC_3_N": "STEP 3", "PROC_3_T": "根拠を構築", "PROC_3_D": "各所見は検証可能な観察と出典に紐付け。",
    "PROC_4_N": "STEP 4", "PROC_4_T": "優先順位付け", "PROC_4_D": "ビジネス影響、工数、確信度で順位付け。",
    "PREVSEC_EYEBROW": "サンプル(レポート予告)", "PREVSEC_H2": "意思決定に使えるSEOレポートとは", "PREVSEC_SUB": "ラベル付きサンプル — 実際のレポートはあなたのサイトに合わせて個別化。",
    "PREV_B4_T": "90日ロードマップ", "PREV_B4_1": "0–30 · 31–60 · 61–90日目、担当者付き",
    "PRICE_EYEBROW": "レポートを選択", "PRICE_H2": "エビデンス主導の2つのレポート。明確な一本道。", "PRICE_SUB": "レポート、言語を選び、安全に支払い。PDFをメールで受取。",
    "PRICE_UNIT": "/ 一回",
    "CARD1_TITLE": "SEO機会診断", "CARD1_WHO": "今後90日でどのSEO作業に注目すべきかを知りたい事業主向け。",
    "CARD1_1": "エビデンス主導のサイト・検索レビュー", "CARD1_2": "優先所見3–5件", "CARD1_3": "トップ5アクションプラン", "CARD1_4": "経営者が読める要約", "CARD1_5": "90日ロードマップ", "CARD1_6": "公開データ検証チェックリスト", "CARD1_CTA": "このレポートを選択",
    "CARD2_BADGE": "実行準備ができたチーム向け", "CARD2_TITLE": "SEO成長ブループリント", "CARD2_WHO": "コンテンツ・マーケ・開発向けのより完全な行動システムが必要なチーム向け。",
    "CARD2_1": "より深い戦略・アーキテクチャ評価", "CARD2_2": "トピック・意図・ページ用途マップ", "CARD2_3": "詳細な優先アクション台帳", "CARD2_4": "コンテンツ機会ブリーフ", "CARD2_5": "開発者向け実装ブリーフ", "CARD2_6": "担当者・検証計画付きの90日ロードマップ", "CARD2_CTA": "このレポートを選択",
    "PRICE_FOOT": "両レポートとも選択した言語でプロ品質のPDFをお届け。",
    "T1_T": "意見より根拠", "T1_D": "所見は推測ではなく観察可能な事実に基づく。",
    "T2_T": "事実と仮定", "T2_D": "事実、推論、仮説を明確にラベル付け。",
    "T3_T": "明確な境界", "T3_D": "検証できること、できないことを正直に提示。",
    "T4_T": "設計上実行可能", "T4_D": "担当者、工数、成功確認方法を記載。",
    "CTA_EYEBROW": "より明確な次の一手", "CTA_H2": "SEOタスクをため込むのはやめ。SEO判断を始めよう。", "CTA_BTN": "レポートを選択",
    "FOOT1": "SEO Scan.ai — エビデンス主導のAI SEO監査レポート",
    "FOOT_PRIVACY": "プライバシーポリシー", "FOOT_TERMS": "利用規約", "FOOT_REFUND": "返金ポリシー", "FOOT_DISCLAIMER": "免責事項",
    "COPYRIGHT": "© 2026 SEO Scan.ai",
    "SCAN_ERR": "スキャンエラー：", "HINT_GOOD": "✅ 健全なサイト", "HINT_MID": "⚠️ 改善の余地あり", "HINT_BAD": "🔴 問題多数", "HINT_NODIAG": "診断を読み取れません",
    "TOP_EMPTY": "明らかな技術エラーを検出せず",
    "CONNECT_ERR": "スキャンサーバーに接続できません：", "EMAIL_REQ": "レポートを受取るメールを入力してください（完全版PDFが届きます）",
    "ORDER_ERR": "注文失敗：", "UNKNOWN_ERR": "不明なエラー",
    "CHECKOUT_PRE": "注文を作成しました（", "CHECKOUT_POST": "）。安全な支払いへ遷移中…",
    "CONNECT_CHECKOUT": "チェックアウトサーバーに接続できません：", "CONNECT_ORDER": "注文サーバーに接続できません：",
})

ES = dict(base("es"), SEL_ES="selected", **{
    "TITLE": "Sepa qué corregir en su web — Informe SEO de decisión basado en evidencia",
    "META_DESC": "Obtenga un informe SEO listo para decidir: sus oportunidades prioritarias, por qué importan a su negocio y un plan de acción de 90 días. Entrega de PDF profesional en su idioma.",
    "NAV_METHOD": "Metodología", "NAV_REPORTS": "Informes", "NAV_PRICE": "Precios",
    "EYEBROW": "Investigación SEO basada en evidencia",
    "H1_L1": "Sepa qué corregir en su web —", "H1_EM": "antes de perder otro mes en SEO.", "H1_L3": "",
    "SUB": "Obtenga un informe SEO listo para decidir que identifica sus oportunidades prioritarias, explica por qué importan y ofrece un plan de acción práctico de 90 días.",
    "HERO_CTA_PRIMARY": "Escanear mi web gratis", "HERO_CTA_SECONDARY": "Ver qué incluye",
    "MICRO1": "Elija su idioma de salida antes del pago", "MICRO2": "Entrega de PDF profesional", "MICRO3": "Sin registro",
    "PREV_LABEL": "Vista previa ilustrativa", "PREV_TITLE": "Diagnóstico de Oportunidades SEO",
    "PREV_B1_T": "Resumen ejecutivo de decisiones", "PREV_B1_1": "Puntuación 64/100 — Necesita mejoras", "PREV_B1_2": "3 hallazgos, est. +9 pts disponibles",
    "PREV_B2_T": "Hallazgo basado en evidencia", "PREV_B2_1": "La velocidad es su mayor freno", "PREV_B2_2": "TTFB medido 1240 ms, sin gzip",
    "PREV_B3_T": "Registro de acciones priorizadas · mapa 90 días", "PREV_B3_1": "Responsable · Esfuerzo · Criterios de aceptación", "PREV_B3_2": "Días 0–30 · 31–60 · 61–90",
    "SCAN_EYEBROW": "Empiece con un escaneo gratis",
    "HOW_H2": "Vea primero sus problemas reales — antes de pagar por nada",
    "HOW_SUB": "Sin registro, sin tarjeta. Pegue la URL de su web y obtenga su puntuación SEO y los problemas principales en segundos.",
    "INPUT_PLACEHOLDER": "Pegue la URL de su web, p. ej. mybusiness.com",
    "SCAN_BTN": "Escanear mi web gratis",
    "RESULT_TITLE": "Resultado del escaneo:",
    "SCORE_LABEL": "Puntuación de salud SEO", "SCORE_HINT": "Escaneando…",
    "TOP_LV": "md", "TOP_PLACEHOLDER": "Introduzca su URL y pulse «Escanear mi web gratis» para ver datos reales de sus problemas principales",
    "LOCK_FIXLIST": "Lista completa de <span class='fixCount'>—</span> correcciones (se actualiza tras escanear)",
    "LOCKED": "Bloqueado", "LOCK_COMPETE": "Análisis comparativo de competidores", "LOCK_AI_STEPS": "Guía de corrección paso a paso con IA + prioridad",
    "EMAIL_NOTE": "Reciba el informe por email (entrega del PDF completo):",
    "CONSENT": "Acepto que mi email se use solo para entregar este informe (ver Política de Privacidad). Puedo darme de baja en cualquier momento.",
    "UNLOCK_BTN": "Desbloquear informe completo",
    "GUARANTEE": "Garantía de 7 días: reembolso total antes de la entrega · revisión gratuita después",
    "AUTO_DELIVER": "Se entrega a su email en unos 10 minutos tras el pago",
    "TA": "Gratis · sin registro · resultado inmediato",
    "DIFF_EYEBROW": "Por qué es distinto", "DIFF_H2": "No es otra exportación de errores SEO.", "DIFF_SUB": "Investigación basada en evidencia, priorizada para su negocio.",
    "D1_T": "Menos ruido", "D1_D": "Riesgos y oportunidades materiales — no una enorme lista genérica de errores.",
    "D2_T": "Evidencia clara", "D2_D": "Hechos, inferencias basadas en evidencia y elementos de validación se mantienen distintos.",
    "D3_T": "Trabajo útil", "D3_D": "Las acciones tienen responsable, esfuerzo, dependencia, criterios de aceptación y validación.",
    "D4_T": "Ante todo negocio", "D4_D": "Las recomendaciones se relacionan con páginas de negocio, recorridos del cliente e intención comercial.",
    "PROC_EYEBROW": "Proceso de investigación", "PROC_H2": "Cómo se construye cada informe", "PROC_SUB": "Un método disciplinado y reproducible — no una suposición automática.",
    "PROC_1_N": "PASO 1", "PROC_1_T": "Estudiar su web", "PROC_1_D": "Leer estructura, navegación y páginas comerciales y de contenido clave.",
    "PROC_2_N": "PASO 2", "PROC_2_T": "Investigar patrones de búsqueda", "PROC_2_D": "Observar qué se posiciona realmente para sus intenciones comerciales.",
    "PROC_3_N": "PASO 3", "PROC_3_T": "Construir la evidencia", "PROC_3_D": "Cada hallazgo se vincula a una observación verificable con fuente.",
    "PROC_4_N": "PASO 4", "PROC_4_T": "Priorizar el trabajo", "PROC_4_D": "Ordenar por impacto comercial, esfuerzo y confianza.",
    "PREVSEC_EYEBROW": "Vista previa ilustrativa", "PREVSEC_H2": "Cómo es un informe SEO listo para decidir", "PREVSEC_SUB": "Muestras claramente etiquetadas — su informe real se personaliza para su web.",
    "PREV_B4_T": "Mapa de acción de 90 días", "PREV_B4_1": "Días 0–30 · 31–60 · 61–90, con responsables",
    "PRICE_EYEBROW": "Elija su informe", "PRICE_H2": "Dos informes basados en evidencia. Un camino claro.", "PRICE_SUB": "Elija informe, idioma y pague de forma segura. Su PDF se entrega por email.",
    "PRICE_UNIT": "/ único",
    "CARD1_TITLE": "Diagnóstico de Oportunidades SEO", "CARD1_WHO": "Para propietarios que necesitan saber qué trabajo SEO merece atención en los próximos 90 días.",
    "CARD1_1": "Revisión basada en evidencia del sitio y la búsqueda", "CARD1_2": "3–5 hallazgos prioritarios", "CARD1_3": "Plan de acción de cinco prioridades", "CARD1_4": "Resumen ejecutivo comprensible para el negocio", "CARD1_5": "Mapa de ruta de 90 días", "CARD1_6": "Lista de verificación de datos públicos", "CARD1_CTA": "Elegir informe",
    "CARD2_BADGE": "Ideal para equipos listos para ejecutar", "CARD2_TITLE": "Blueprint de Crecimiento SEO", "CARD2_WHO": "Para equipos que necesitan un sistema de acción más completo para contenido, marketing y desarrollo.",
    "CARD2_1": "Evaluación más profunda de estrategia y arquitectura", "CARD2_2": "Mapa de temas, intención y propósito de página", "CARD2_3": "Registro de acciones priorizadas detallado", "CARD2_4": "Briefs de oportunidad de contenido", "CARD2_5": "Briefs de implementación listos para desarrolladores", "CARD2_6": "Mapa de 90 días con responsables y plan de validación", "CARD2_CTA": "Elegir informe",
    "PRICE_FOOT": "Ambos informes se entregan como PDF profesional en el idioma que elija.",
    "T1_T": "Evidencia antes que opinión", "T1_D": "Los hallazgos se apoyan en hechos observables, no en conjeturas.",
    "T2_T": "Hechos frente a supuestos", "T2_D": "Hecho, inferencia e hipótesis se etiquetan claramente.",
    "T3_T": "Límites claros", "T3_D": "Lo que podemos y no podemos verificar se indica con honestidad.",
    "T4_T": "Accionable por diseño", "T4_D": "Se incluyen responsable, esfuerzo y cómo comprobar el éxito.",
    "CTA_EYEBROW": "Un camino más claro", "CTA_H2": "Deje de acumular tareas SEO. Empiece a tomar decisiones SEO.", "CTA_BTN": "Elija su informe",
    "FOOT1": "SEO Scan.ai — Informe SEO de auditoría asistido por IA y basado en evidencia",
    "FOOT_PRIVACY": "Política de privacidad", "FOOT_TERMS": "Términos de servicio", "FOOT_REFUND": "Política de reembolso", "FOOT_DISCLAIMER": "Aviso legal",
    "COPYRIGHT": "© 2026 SEO Scan.ai",
    "SCAN_ERR": "Error de escaneo:", "HINT_GOOD": "✅ Sitio saludable", "HINT_MID": "⚠️ Merece mejorar", "HINT_BAD": "🔴 Muchos problemas", "HINT_NODIAG": "No se pudo leer el diagnóstico",
    "TOP_EMPTY": "No se detectaron errores técnicos evidentes",
    "CONNECT_ERR": "No se pudo conectar con el servidor de escaneo:", "EMAIL_REQ": "Introduzca el email para recibir el informe (el PDF completo llega aquí)",
    "ORDER_ERR": "Error al crear el pedido:", "UNKNOWN_ERR": "error desconocido",
    "CHECKOUT_PRE": "Pedido creado (", "CHECKOUT_POST": "). Redirigiendo a pago seguro…",
    "CONNECT_CHECKOUT": "No se pudo conectar con el servidor de checkout:", "CONNECT_ORDER": "No se pudo conectar con el servidor de pedidos:",
})

LANGS = {
    "landing_page.html":    EN,
    "landing_en.html":      EN,
    "landing_zh-Hant.html": ZH_HANT,
    "landing_zh-Hans.html": ZH_HANS,
    "landing_ja.html":      JA,
    "landing_es.html":      ES,
}

def render(tokens):
    html = SKELETON
    for k, v in tokens.items():
        html = html.replace("{{" + k + "}}", str(v))
    # price tokens come from config (single source)
    import config as _cfg
    html = html.replace("{{PRICE_USD}}", str(_cfg.DEFAULT_PRICE_USD))
    html = html.replace("{{EARLY_PRICE_USD}}", str(_cfg.EARLY_PRICE_USD))
    html = html.replace("{{GROWTH_PRICE_USD}}", str(_cfg.GROWTH_PRICE_USD))
    html = html.replace("{{REGULAR_PRICE_USD}}", str(_cfg.REGULAR_PRICE_USD))
    import re
    leftovers = re.findall(r"\{\{[A-Z0-9_]+\}\}", html)
    leftovers = [x for x in leftovers if x not in ("{{URL_PATH}}", "{{BASE_URL}}")]
    if leftovers:
        raise RuntimeError("Missing tokens: " + ", ".join(sorted(set(leftovers))))
    return html

def main():
    BASE = "https://seoscanaudit.com"
    URL_PATHS = {
        "landing_page.html": "", "landing_en.html": "",
        "landing_zh-Hant.html": "zh-Hant", "landing_zh-Hans.html": "zh-Hans",
        "landing_ja.html": "ja", "landing_es.html": "es",
    }
    for fname, tokens in LANGS.items():
        html = render(tokens)
        up = URL_PATHS.get(fname, "")
        html = html.replace("{{URL_PATH}}", up)
        html = html.replace("{{BASE_URL}}", BASE)
        path = os.path.join(HERE, fname)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"wrote {fname} ({len(html)} bytes)")

if __name__ == "__main__":
    main()