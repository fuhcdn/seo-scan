"""site_profiler.py — 網站指紋分型 + 個性化權重。

將 crawler 出嚟嘅 signals 分析成「網站類型」，並為每個類型產生個性化權重，
令兩個唔同網站即使部分 counter 相同，報告嘅「點解同優先次序」都唔同——
呢個係殺死「攞乜網站都一樣分」死症嘅核心。

Deterministic（唔用 LLM），成本 $0，純規則分析。
"""


def classify_site(signals: dict) -> dict:
    """根據 signals 判網站類型，返回個性化 profile。

    Returns:
        {
          "site_type": "ecommerce"|"content"|"local_service"|"saas"|"corporate"|"unknown",
          "labels": [str, ...],          # 人類可讀標籤（報告 header 用）
          "weights": {str: float},       # 個性化權重（keys 對應報告 section）
          "persona_note": str,           # 一句「你係邊種網站」——報告開頭用
        }
    """
    json_ld = signals.get("json_ld") or []
    og = signals.get("open_graph") or {}
    title = (signals.get("title") or "").lower()
    h1 = " ".join(signals.get("h1") or []).lower()
    url = signals.get("url") or ""
    imgs = signals.get("img_total") or 0
    internal = signals.get("internal_link_count") or 0
    external = signals.get("external_link_count") or 0

    # 收集 JSON-LD @type
    json_types = set()
    for b in json_ld:
        if isinstance(b, dict):
            t = b.get("@type")
            json_types.update([t] if isinstance(t, str) else (t or []))
    types_l = {str(t).lower() for t in json_types}

    has_product = bool(types_l & {"product", "offer", "aggregaterating",
                                  "store", "productgroup"})
    has_article = bool(types_l & {"article", "blogposting", "newsarticle"})
    has_review = bool(types_l & {"review", "localbusiness", "medicalbusiness",
                                 "dentist", "restaurant", "hair salon",
                                 "automotivebusiness", "healthandbeautybusiness"})
    has_software = bool(types_l & {"softwareapplication", "webapplication",
                                   "product"} and "pricing" in title + h1)

    # 文字+URL 線索
    text = (title + " " + h1).lower()
    ecom_kw = any(k in text or k in url for k in
                  ["shop", "store", "cart", "buy", "product", "checkout", "basket"])
    blog_kw = any(k in text or k in url for k in
                  ["blog", "article", "post", "news", "journal", "magazine"])
    local_kw = any(k in text for k in
                   ["gallery", "clinic", "studio", "salon", "restaurant", "dental",
                    "plumbing", "lawyer", "law firm", "在線", "線上", "預約", "診所",
                    "美容", "餐廳", "報價"])
    saas_kw = any(k in text for k in
                  ["pricing", "login", "sign up", "dashboard", "app", "software",
                   "subscription", "免費試用", "登入", "方案", "定價"])

    # 決定網站類型（優先順序）
    if has_product or (ecom_kw and not blog_kw):
        site_type = "ecommerce"
    elif has_article or blog_kw:
        site_type = "content"
    elif has_review or local_kw:
        site_type = "local_service"
    elif has_software or saas_kw:
        site_type = "saas"
    elif has_product:
        site_type = "ecommerce"
    else:
        site_type = "corporate"

    # 每個類型嘅個性化權重（影響 fix 排序/優先次序）
    weights = {
        # keys: meta / content / technical / links / speed / schema / local
        "ecommerce":     {"meta": 0.15, "content": 0.15, "technical": 0.20,
                          "links": 0.10, "speed": 0.15, "schema": 0.20, "local": 0.05},
        "content":       {"meta": 0.10, "content": 0.40, "technical": 0.15,
                          "links": 0.25, "speed": 0.05, "schema": 0.05, "local": 0.00},
        "local_service": {"meta": 0.10, "content": 0.10, "technical": 0.15,
                          "links": 0.10, "speed": 0.10, "schema": 0.20, "local": 0.25},
        "saas":          {"meta": 0.15, "content": 0.20, "technical": 0.25,
                          "links": 0.10, "speed": 0.15, "schema": 0.15, "local": 0.00},
        "corporate":     {"meta": 0.15, "content": 0.20, "technical": 0.25,
                          "links": 0.15, "speed": 0.15, "schema": 0.10, "local": 0.00},
    }
    personas = {
        "ecommerce":     "你係一個網上商店/電商網站——產品頁同分類頁嘅 schema、速度同可否被收錄，直接決定你賣到幾多貨。",
        "content":       "你係一個內容/媒體網站——文章深度、E-E-A-T 同內部連結，決定你嘅內容可唔可以排前同留住讀者。",
        "local_service": "你係一個本地服務商——Google 商家資料、Location schema、地圖同本地搜尋，先係你嘅命脈。",
        "saas":          "你係一個軟件/工具網站——定價頁嘅可收錄性、速度同轉化頁面結構，直接影響你簽到幾多客。",
        "corporate":     "你係一間企業官網——技術健康、內容深度同權威信號，決定你喺行業搜尋中嘅信任度。",
    }
    labels = {
        "ecommerce": ["電商/商店", "E-commerce", "Product rich results"],
        "content":   ["內容/媒體", "Content & Blog", "E-E-A-T"],
        "local_service": ["本地服務商", "Local Business", "Google Business Profile"],
        "saas":      ["SaaS/軟件", "Software", "Pricing & Conversion"],
        "corporate": ["企業官網", "Corporate Site", "Authority"],
    }

    return {
        "site_type": site_type,
        "labels": labels.get(site_type, ["網站", "Website"]),
        "weights": weights.get(site_type, weights["corporate"]),
        "persona_note": personas.get(site_type, personas["corporate"]),
    }


def unique_evidence_count(signals: dict) -> int:
    """質量 Gate A：數 signals 入面有幾多條『site-specific 實測證據』。

    呢啲先係令報告唔係模板嘅關鍵——每個網站都唔同嘅實測值。
    """
    count = 0
    checks = [
        ("title", lambda v: bool(v)),
        ("meta_description", lambda v: bool(v)),
        ("h1_count", lambda v: v and v > 0),
        ("h2_count", lambda v: v is not None),
        ("img_total", lambda v: v is not None),
        ("img_missing_alt", lambda v: v is not None),
        ("internal_link_count", lambda v: v is not None),
        ("external_link_count", lambda v: v is not None),
        ("canonical", lambda v: bool(v)),
        ("has_lang_attr", lambda v: v is not None),
        ("viewport", lambda v: bool(v)),
        ("json_ld", lambda v: bool(v)),
    ]
    for key, test in checks:
        try:
            if test(signals.get(key)):
                count += 1
        except Exception:
            pass
    return count