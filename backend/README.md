# Backend

## Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Fill in your API keys
uvicorn app.main:app --reload
```

## API Endpoints
- `POST /api/v1/agent/process-audio` - Upload audio, get explanation + email draft
