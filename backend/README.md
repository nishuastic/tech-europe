# Backend

## Setup
```bash
cd backend
# IMPORTANT: Always use `uv` for dependency management
uv sync
source .venv/bin/activate
cp .env.example .env  # Fill in your API keys
uvicorn app.main:app --reload
```

## API Endpoints
- `POST /api/v1/agent/process-audio` - Upload audio, get explanation + email draft
