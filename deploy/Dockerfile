# SEO Scan — Render deploy
# 純 stdlib Python (無第三方依賴)
FROM python:3.11-slim

WORKDIR /app

# Copy 成個 pipeline
COPY pipeline/ ./pipeline/

WORKDIR /app/pipeline

# Render 會檢查 PORT env；server.py 已讀 PORT
EXPOSE 8000

CMD ["python3", "server.py"]