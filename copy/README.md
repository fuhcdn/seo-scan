# copy/ — 安全副本區 (Safety Snapshot)

**用途:** 任何要「郁手改得嚟有風險」嘅檔案,先複製一份落嚟,出事即刻還原。

**點用:**
- 改 server.py / config.py / render.yaml 等之前 → 先 backup 入嚟
- 用 `yyyy-mm-dd` 開子資料夾,例如 `copy/2026-09-12/`
- 出事:用 `cp copy/2026-09-12/server.py pipeline/server.py` 還原

**唔放入嚟:** secrets.env（機密,另外安全處理）、output/、logs/
