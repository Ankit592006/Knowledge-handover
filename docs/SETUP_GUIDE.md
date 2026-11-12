# Setup Guide — Knowledge Handover Platform

## 1. Prerequisites
- Python 3.11+
- Node.js 20+ and npm
- Docker & Docker Compose (for PostgreSQL 16 + `pgvector` container)
- Optional: Ollama (`ollama pull qwen2.5:7b-instruct`) for live local open-source LLM inference

## 2. Environment Setup
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

## 3. Running with Docker Compose
```bash
docker compose up --build
```

## 4. Running Locally (Without Docker)
The backend automatically uses a local SQLite database (`knowledge_handover_dev.db`) with cross-dialect vector support if `DATABASE_URL` is not pointed at PostgreSQL, so you can run the entire stack immediately:
```bash
# Terminal 1: Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```
