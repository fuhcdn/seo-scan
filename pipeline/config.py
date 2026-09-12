#!/usr/bin/env python3
"""config.py — 單一來源定價（single source of truth）。

整個生意（收款 pipeline + landing page）嘅價格都由呢個檔一齊讀，
避免 runner 硬編 US$99 而 landing 又寫另一啲，兩個唔同步。

可用環境變數覆寫（例如臨時轉價、測試）：
    DEFAULT_PRICE_USD  = 實際收款單價（單頁 intro 期）  [default 79]
    REGULAR_PRICE_USD  = 正價（strikethrough 原價）          [default 99]
    INTRO_DISCOUNT_USD = 早鳥折讓額 = REGULAR - DEFAULT     [default 20]

用法（喺 runner / landing renderer 都 import 同一 config）：
    from config import DEFAULT_PRICE_USD, REGULAR_PRICE_USD, INTRO_DISCOUNT_USD
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _int_env(name, default):
    try:
        return int(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


# 單頁完整 SEO 審計報告 —— 實收單價（單頁 intro 期）。
# Round2 修正：由硬編碼 US$99 改成單一來源，預設 US$79（首 20 位 intro 價）。
DEFAULT_PRICE_USD = _int_env("DEFAULT_PRICE_USD", 79)

# 正價（頁面上會用刪除線顯示嘅「原價」）。
REGULAR_PRICE_USD = _int_env("REGULAR_PRICE_USD", 99)

# 早鳥折讓額（面頁顯示「-US$20」）。
INTRO_DISCOUNT_USD = _int_env("INTRO_DISCOUNT_USD",
                              max(0, REGULAR_PRICE_USD - DEFAULT_PRICE_USD))

# -------------------------------
# Landing page（同一價格來源）
# -------------------------------
# 源模板：含 {{PRICE_USD}} / {{REGULAR_PRICE_USD}} / {{INTRO_DISCOUNT_USD}} 佔位符。
# render_landing() 用上面嘅 config 值填好 → 輸出 landing_page.html，
# 咁個 landing 分分鐘同 runner 收款價格自動保持一致。
LANDING_TEMPLATE = os.path.join(_HERE, "landing_page.template.html")
LANDING_OUT      = os.path.join(_HERE, "landing_page.html")


def render_landing(output_path=None):
    """用 config 嘅價格填 landing 模板，輸出可 serve 嘅 landing_page.html。

    Round5：render 後會檢查輸出唔可以係示範模式（DEMO_MODE=false），
    防止真後端被 template 嘅 demo 兜返貼提 —— 撞到 demo 會 raise，唔出檔。

    Return: 寫好嘅檔案路徑（寫唔到 / 發現 demo 模式就會 raise）。"""
    with open(LANDING_TEMPLATE, "r", encoding="utf-8") as fh:
        html = fh.read()
    html = html.replace("{{PRICE_USD}}", str(DEFAULT_PRICE_USD))
    html = html.replace("{{REGULAR_PRICE_USD}}", str(REGULAR_PRICE_USD))
    html = html.replace("{{INTRO_DISCOUNT_USD}}", str(INTRO_DISCOUNT_USD))

    # Round5 防回歸：模板必須係真後端（DEMO_MODE=false），一旦 render 出嚟撞到示範
    # 模式（DEMO_MODE=true）就代表 template 回歸咗 demo，即刻警告並拒絕寫檔。
    if "var DEMO_MODE = false;" not in html or "var DEMO_MODE = true;" in html:
        raise RuntimeError(
            "landing template 回歸咗示範模式（DEMO_MODE=true）。"
            "請修正 landing_page.template.html 用真實 /api/scan 嘅 runScan，"
            "確認 var DEMO_MODE = false; 先可以 render。")

    out = output_path or LANDING_OUT
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out


if __name__ == "__main__":
    print("DEFAULT_PRICE_USD   =", DEFAULT_PRICE_USD)
    print("REGULAR_PRICE_USD   =", REGULAR_PRICE_USD)
    print("INTRO_DISCOUNT_USD  =", INTRO_DISCOUNT_USD)
    p = render_landing()
    print(f"landing rendered -> {p}")