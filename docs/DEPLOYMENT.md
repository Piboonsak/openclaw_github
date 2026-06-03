# Deployment Guide (Draft)

## Local Deployment
1. Set environment variables from `config/.env.example`
2. Install dependencies from `requirements.txt`
3. Start API server:

```bash
uvicorn src.api.endpoints:app --host 0.0.0.0 --port 8000
```

## Recommended Production Setup
- Reverse proxy (Nginx)
- Process manager (systemd or container orchestration)
- Secrets from secure store (not in `.env` committed files)
- Monitoring for OCR/extraction latency and failure rates
