# Setup Guide

## Prerequisites

- Python 3.12+ (for Gradium SDK)
- Node.js 18+ / Bun
- API Keys: Gradium, Dify

---

## 1. Backend Setup

```bash
cd backend

# Use uv (recommended)
uv venv --python 3.12
uv pip install -r requirements.txt

# Or use pip
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:
```env
GRADIUM_API_KEY=gd_your_key_here
DIFY_API_KEY=app-your_key_here
DIFY_API_URL=https://api.dify.ai/v1
```

### Run Backend

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/health`

---

## 2. Frontend Setup

```bash
cd bureaucracy-buddy

# Install dependencies
npm install
# or
bun install

# Run dev server
npm run dev
```

Frontend runs at: http://localhost:5173

### Connect to Backend

Update the API URL in your frontend code to point to:
```
http://localhost:8000/api/v1/agent/process-audio
```

---

## 3. Dify Setup

1. Go to [dify.ai](https://dify.ai)
2. Create new **Chatflow** or **Agent**
3. **Knowledge Base**: Import URLs from `docs/dify_knowledge_urls.txt`
4. **System Prompt**: Copy from `docs/dify_system_prompt.md`
5. **Publish** and copy API Key to `.env`

---

## 4. Test the Full Stack

1. Start backend: `uvicorn app.main:app --reload`
2. Start frontend: `npm run dev`
3. Open http://localhost:5173
4. Click the microphone and speak!

---

## 5. Alpic Skybridge Setup (ChatGPT App)

1.  **Run Locally**:
    ```bash
    cd skybridge-app
    npm install
    npm run dev
    # Runs on http://localhost:3000
    ```

2.  **Expose Backend**:
    - Run `ngrok http 8000`
    - Copy the `https://...` URL

3.  **Deploy to Alpic Cloud**:
    - Push code to GitHub.
    - Go to [app.alpic.ai](https://app.alpic.ai).
    - Import project `skybridge-app`.
    - **Settings -> Environment Variables**:
        - `BACKEND_URL`: Your ngrok URL (e.g., `https://xxxx.ngrok-free.app`)
    - Deploy!

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: gradium` | Use Python 3.12: `uv venv --python 3.12` |
| CORS errors | Backend already has CORS configured for localhost |
| Dify timeout | Check your API key and Dify workflow is published |
