FROM python:3.11-slim
WORKDIR /app
# headless Chromium for HTML->PDF report generation
RUN pip install --no-cache-dir pypdf==6.18.1 pdfplumber==0.11.4

RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        fonts-liberation \
        fonts-noto-cjk \
        libasound2 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        xdg-utils \
    && rm -rf /var/lib/apt/lists/*
COPY pipeline/ ./pipeline/
COPY gates/ ./gates/
COPY tests/ ./tests/
WORKDIR /app/pipeline
EXPOSE 8000
CMD ["python3", "server.py"]