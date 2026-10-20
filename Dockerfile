Multi-stage build for MedDRA Coding Assistant v2.0

FROM python:3.11-slim AS builder

WORKDIR /tmp

RUN apt-get update && apt-get install -y –no-install-recommends 
gcc 
g++ 
&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install –user –no-cache-dir -r requirements.txt

Final stage

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y –no-install-recommends 
curl 
&& rm -rf /var/lib/apt/lists/*

COPY –from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

Copy application files

COPY app/ /app/app/
COPY static/ /app/static/
COPY scripts/ /app/scripts/

Copy MedDRA data

RUN mkdir -p /data
COPY data/meddra_terms.jsonl.gz /data/meddra_terms.jsonl.gz

EXPOSE 8000

HEALTHCHECK –interval=30s –timeout=10s –start-period=40s –retries=3 
CMD curl -f http://localhost:8000/health || exit 1

Start FastAPI with an ASGI server

CMD [“python”, “-m”, “uvicorn”, “app.main:app”, “–host”, “0.0.0.0”, “–port”, “8000”]
