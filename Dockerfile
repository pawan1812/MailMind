# Stage 1: dependencies
FROM python:3.11-slim AS builder
WORKDIR /install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: production
FROM python:3.11-slim AS production

# Non-root user (HuggingFace Spaces requirement)
RUN useradd -m -u 1000 mailmind
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=mailmind:mailmind . .

USER mailmind
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import httpx; r=httpx.get('http://localhost:7860/health'); exit(0 if r.status_code==200 else 1)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
