#!/usr/bin/env python3
"""product_catalog.py — 內部產品目錄 + 報告層級路由（single source of truth）。

按 HERMES MASTER INSTRUCTION A2：唔准硬編/估價，runtime 由 selected_product_id
讀內部目錄，map 去 ENTRY_REPORT 或 PREMIUM_REPORT。產品本身價格/price_id dev 唔喺度估。

Confirmed by Yan (2026-09-12): ENTRY = $397/$497 (SEO Opportunity Diagnostic),
PREMIUM = $997 (SEO Growth Blueprint).
"""
import os

_ENV = os.environ

# 五種配置好嘅輸出語言（唯一清單，不可亂加/刪/改名）
REPORT_LANGUAGES = ("en", "zh-Hant", "zh-Hans", "ja", "es")

# 內部產品目錄 —— 每個產品：id / display name / tier / 環境變數 pointer 去佢嘅
# Stripe price id（price 實際值歸 Stripe + secrets.env，呢度淨係 routing）。
PRODUCT_CATALOG = {
    "prod_seo_opportunity": {         # ENTRY — SEO Opportunity Diagnostic
        "name": "SEO Opportunity Diagnostic",
        "tier": "ENTRY_REPORT",
        "price_env": "PRICE_397",     # $397 early / fallback PRICE_497
        "price_fallback_env": "PRICE_497",
        "skill": "ENTRY_REPORT_SKILL",
    },
    "prod_seo_growth": {              # PREMIUM — SEO Growth Blueprint
        "name": "SEO Growth Blueprint",
        "tier": "PREMIUM_REPORT",
        "price_env": "PRICE_997",
        "price_fallback_env": "PRICE_997",
        "skill": "PREMIUM_REPORT_SKILL",
    },
}
# Stripe price ID（線路層由 /api/create-checkout 讀 env，唔喺呢度寫死值）
# price price_id 由 secrets.env 嘅 PRICE_397/497/997 提供。


def valid_language(lang):
    return isinstance(lang, str) and lang in REPORT_LANGUAGES


def product_exists(product_id):
    return product_id in PRODUCT_CATALOG


def get_product(product_id):
    return PRODUCT_CATALOG.get(product_id)


def get_tier(product_id):
    """由內部目錄 map selected_product_id -> ENTRY_REPORT / PREMIUM_REPORT。
    未知產品 -> None (caller 要 stop + log PRODUCT_MAPPING_ERROR)。"""
    p = PRODUCT_CATALOG.get(product_id)
    return p["tier"] if p else None


def price_point_for(product_id, early=False):
    """回傳 (price_usd_int, env_key)。讀 config 實際金額（唔喺呢度估）。
    ENTRY 早鳥 -> EARLY_PRICE_USD, 正價 -> DEFAULT/REGULAR；PREMIUM -> GROWTH。"""
    p = PRODUCT_CATALOG.get(product_id)
    if not p:
        return None, None
    try:
        import config as _cfg
        if p["tier"] == "PREMIUM_REPORT":
            return int(_cfg.GROWTH_PRICE_USD), "PRICE_997"
        # ENTRY：early 用 EARLY_PRICE_USD（$397），否則 DEFAULT（$497）
        return (int(_cfg.EARLY_PRICE_USD) if early else int(_cfg.DEFAULT_PRICE_USD)), \
               (p["price_env"] if early else p["price_fallback_env"])
    except Exception:
        return None, None


def price_id_for(product_id, early=False):
    """Stripe price id —— 由 secrets.env 嗰個 env key 讀（routing 只有 key，
    實際 id 喺 secrets.env，唔喺呢度硬編）。"""
    _usd, env_key = price_point_for(product_id, early=early)
    if not env_key:
        return None
    return _ENV.get(env_key, "").strip() or None


if __name__ == "__main__":
    print("languages:", REPORT_LANGUAGES)
    for pid, p in PRODUCT_CATALOG.items():
        usd, env = price_point_for(pid)
        print(f"{pid}: tier={p['tier']} price~${usd} env={env} lang_ok={valid_language('en')}")