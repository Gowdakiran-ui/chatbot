# Chanakya

Internal RAG assistant for Onlyne Reputation, one app with two modes:

- **Chanakya**: career, leadership and ethics advice grounded in the Arthashastra and Chanakya Niti, restated for modern business.
- **Crisis Advisor**: precedent-based guidance from past PR and reputation crises.

Each mode has its own knowledge base and system prompt. Every question is answered on its own; the backend keeps no conversation history. Chat history shown in the UI lives in the user's browser (`localStorage`).

```
frontend/   React + Vite + Tailwind SPA (TypeScript)
serving/    FastAPI backend: POST /chat, streams Server-Sent Events
db/         Qdrant clients, hybrid retrieval, ingestion scripts
providers/  Generation provider (OpenRouter) behind a thin interface
prompts/    chanakya_system.md, crisis_system.md
scripts/    issue_token.py (client access tokens)
```

## Run locally (Windows)

```bat
install.bat      :: creates .venv, installs backend + frontend deps, creates .env files
start.bat        :: backend on :8000, frontend on :5173, opens the browser
```

Fill in `.env` (copy of `.env.example`) with real credentials first. With `AUTH_DISABLED=true` in `.env` and `VITE_AUTH_DISABLED=true` in `frontend/.env` (the defaults) no token is needed. **Never deploy with either set to true.**

Manual equivalent:

```bash
pip install -r serving/requirements.txt
uvicorn serving.app:app --port 8000          # from the repo root
cd frontend && npm install && npm run dev    # http://localhost:5173
```

In dev, Vite proxies `/api/*` to `localhost:8000` and strips the `/api` prefix: the browser calls `/api/chat`, the backend serves `/chat`.

### Tests

```bash
pip install -r serving/requirements-dev.txt  # adds pytest
python -m pytest serving providers           # backend (set AUTH_DISABLED=false for a fully clean run)
cd frontend && npm test                      # frontend unit tests (vitest)
```

## Configuration

Backend (`.env` in the repo root, see `.env.example`):

| Variable | Purpose |
|---|---|
| `chanakya_qdrant_url`, `chanakya_qdrant_api_key` | Chanakya knowledge base (Qdrant Cloud) |
| `crisis_planer_qdrant_url`, `crisis_planer_api_key` | Crisis knowledge base (Qdrant Cloud) |
| `open_router_api_key`, `openrouter_model` (optional) | Generation via OpenRouter |
| `AUTH_DISABLED` | `true` skips token auth (local review only) |
| `ALLOWED_ORIGINS` | CORS allow-list. Not needed when the SPA and API share an origin behind the proxy. |

Frontend (`frontend/.env`, see `frontend/.env.example`; values are baked in at build time):

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | API base. Default `/api` (same origin behind the reverse proxy). |
| `VITE_AUTH_DISABLED` | `true` hides the token screen. Must be `false` (or unset) for production. |

Issue a client access token (printed once, stored hashed in `data/auth.db`):

```bash
python -m scripts.issue_token acme_corp "Acme Corp"
```

## Deploy (small VM)

The VM only serves files and runs the API. **Build the frontend on your own machine** and copy `frontend/dist/` up:

```bash
cd frontend && npm ci && npm run build      # output: frontend/dist/
```

### nginx

Serves `dist/` and proxies `/api/` to the backend. `proxy_buffering off` matters: with buffering on, nginx holds the whole streamed answer and the user sees nothing until it finishes.

```nginx
server {
    listen 80;
    server_name chanakya.example.com;          # add TLS (certbot) before real use

    root /var/www/chanakya;                    # contents of frontend/dist
    index index.html;

    location / {
        try_files $uri /index.html;
    }

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /api/ {
        rewrite ^/api/(.*)$ /$1 break;         # backend routes have no /api prefix
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Connection "";

        proxy_buffering off;                   # required for streaming
        proxy_cache off;
        gzip off;
        proxy_read_timeout 180s;               # crisis answers can take 30-40 s
        client_max_body_size 64k;
    }
}
```

Caddy equivalent:

```caddy
chanakya.example.com {
    root * /var/www/chanakya
    handle_path /api/* {
        reverse_proxy 127.0.0.1:8000 {
            flush_interval -1
        }
    }
    try_files {path} /index.html
    file_server
}
```

### systemd (single worker)

`/etc/systemd/system/chanakya.service`:

```ini
[Unit]
Description=Chanakya API
After=network.target

[Service]
User=chanakya
WorkingDirectory=/opt/chanakya
EnvironmentFile=/opt/chanakya/.env
ExecStart=/opt/chanakya/.venv/bin/uvicorn serving.app:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Keep it to **one worker**: the rate limiter and generation-concurrency cap are in-process, so extra workers would each get their own limits (and each would load its own embedding models).

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now chanakya
```

### Before going live

- Set `AUTH_DISABLED=false` in `.env` and build the frontend with `VITE_AUTH_DISABLED=false`. Issue tokens with `scripts.issue_token`.
- Serve over HTTPS (tokens travel in an `Authorization` header).
- Copy `.env.example` to `.env` on the server and fill in real keys; never commit `.env`.

### Resource notes

- **Memory: the backend does not fit a 1 GB machine.** Retrieval embeds each query locally with `nomic-embed-text-v1.5` (`sentence-transformers` + `torch`) plus a `fastembed` BM25 model, loaded into the API process. Measured on Windows with one real retrieval per mode: ~470 MB resident just after importing the app (torch), **peak ~1.6 GB** while the models load on the first request, **~1.0 GB steady state**. Plan for a 4 GB machine (2 GB is tight), or move query embedding to a hosted service. A t2.micro (1 GB, no swap) will be killed by the OOM killer. First request after a restart is also slow (~15 s model load); consider warming it with one request after deploy.
- **Cost/abuse:** the API already has per-client rate limiting (30 requests/min) and a global cap of 4 concurrent generations. With ~100 users and a limited OpenRouter budget, keep auth on and watch OpenRouter spend; consider a per-client daily cap.
