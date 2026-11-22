# Ask Corvalis

An internal knowledge assistant for Corvalis staff: ask a question in plain language, get a short answer with the source it came from.

## Problem & why

_TODO_

## For whom

_TODO_

## What it does

_TODO_

## How to run

### Requirements

- Python 3.11+
- Node.js 20+

### Backend

```
cd backend
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Optional: local AI model (Ollama)

The app works fully without it (it then shows the matching policy section). With it, answers are short sentences written from the sources.

1. Install Ollama: check with `ollama --version`. If missing:
   - Windows: `winget install Ollama.Ollama` (or https://ollama.com/download)
   - macOS: `brew install ollama`
   - Linux: `curl -fsSL https://ollama.com/install.sh | sh`
2. Pull a small model: `ollama pull llama3.2:3b` (~2 GB).
   On a slow or low-RAM machine use `ollama pull qwen2.5:1.5b` (~1 GB) and set `OLLAMA_MODEL=qwen2.5:1.5b` before starting the backend.
3. Verify: `ollama run llama3.2:3b "Say hi in 3 words"` responds, and http://localhost:11434/api/tags lists the model.

## What works

_TODO_

## What's missing

_TODO_

## Next steps

_TODO_

## How I used AI

_TODO_
