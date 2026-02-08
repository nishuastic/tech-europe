# AdminHero - Voice-First French Bureaucracy Copilot

> Navigate French Bureaucracy. In Any Language.

## Quick Start

```bash
# Terminal 1: Backend
cd backend
# IMPORTANT: Always use `uv` for backend dependencies!
uv sync
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd bureaucracy-buddy
npm install  # or bun install
npm run dev

# Terminal 3: Alpic Skybridge (Optional)
cd skybridge-app
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  bureaucracy-   │────▶│    FastAPI      │────▶│     Dify        │
│     buddy       │     │    Backend      │     │   (RAG + LLM)   │
│  (Vite/React)   │◀────│   :8000         │◀────│                 │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 ▲
                        ┌────────┴────────┐
                        │    Gradium      │
                        │   (STT + TTS)   │
                        └────────┬────────┘
                                 ▲
                        ┌────────┴────────┐
                        │    Alpic App    │
                        │   (Skybridge)   │
                        └─────────────────┘
```

## Project Structure

```
tech-europe/
├── backend/               # FastAPI (Python 3.12)
│   ├── app/
│   │   ├── api/v1/       # API routes
│   │   ├── services/     # Gradium, Dify integrations
│   │   └── config.py     # Settings
│   └── .env              # API keys (git-ignored)
├── bureaucracy-buddy/     # Frontend (Vite + React + shadcn)
│   ├── src/
│   └── package.json
├── skybridge-app/         # Alpic Skybridge App (ChatGPT Integration)
│   ├── server/
│   ├── web/
│   └── package.json
└── docs/                  # Setup guides & prompts
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/agent/process-audio` | Upload audio → Get explanation + email draft |

## Environment Variables (backend/.env)

```env
GRADIUM_API_KEY=gd_xxx
DIFY_API_KEY=app-xxx
DIFY_API_URL=https://api.dify.ai/v1
```

## Docs

- [Setup Guide](docs/SETUP.md)
- [Roadmap](docs/ROADMAP.md)

## License

MIT
