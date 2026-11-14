# Setup & Cloud Deployment Guide — Knowledge Handover Platform (Continuity OS v2.1)

## 1. Prerequisites
- **Python 3.11+**
- **Node.js 20+** and `npm`
- **Optional**: Docker & Docker Compose (for local PostgreSQL 16 + `pgvector` container)
- **Optional LLM Runtime**:
  - **Cloud OpenAI-Compatible (Default)**: Groq API key (`gsk_...`) with `LLM_PROVIDER="openai_compatible"`, `LLM_BASE_URL="https://api.groq.com/openai/v1"`, and `LLM_MODEL_NAME="llama-3.3-70b-versatile"`.
  - **Local Ollama**: `ollama pull qwen2.5:7b-instruct` with `LLM_PROVIDER="ollama"`.
  - **Zero-Key Offline Mode**: Automatically falls back to `rule-grounded-extractor-v1` when `LLM_API_KEY` is empty.

## 2. Environment Setup
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

## 3. Running Locally (Zero-Friction SQLite or PostgreSQL)
The backend automatically uses a local SQLite database (`knowledge_handover_dev.db`) with cross-dialect vector support if `DATABASE_URL` is not pointed at PostgreSQL:
```bash
# Terminal 1: Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```
- **Frontend UI**: `http://localhost:5173`
- **Backend Swagger Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/api/v1/health`

## 4. Running with Docker Compose (PostgreSQL 16 + `pgvector` + Nginx SPA)
```bash
docker compose up --build
```

## 5. Production Deployment on Render (`render.yaml`)
1. Push the repository to GitHub (`https://github.com/Ankit592006/Knowledge-handover.git`).
2. In the Render Dashboard, create a **Blueprint** from `render.yaml` (provisions `kh-postgres`, `kh-backend`, and `kh-frontend`).
3. In `kh-backend` → **Environment**, set:
   - `LLM_PROVIDER` = `openai_compatible`
   - `LLM_BASE_URL` = `https://api.groq.com/openai/v1`
   - `LLM_MODEL_NAME` = `llama-3.3-70b-versatile`
   - `LLM_API_KEY` = `<your_groq_api_key>`
4. Verify live status at `https://kh-backend-z2o3.onrender.com/api/v1/health`.
