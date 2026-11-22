# Ask Corvalis

An internal knowledge assistant for Corvalis staff. Type a question in plain English and get a short answer, together with the source it came from:

- **Company rules**: "How many days of annual leave do I get?" → answer + the policy section it comes from.
- **Past projects**: "Have we designed a timber footbridge before?" → the matching past projects, with project manager, year and folder path.

It runs entirely on a laptop. The AI model is local (Ollama) and **optional**: without it, the app still answers by showing the matching policy section or project cards.

## Problem & why

Corvalis is a 50-person engineering consultancy (Brussels & Liège) where everything runs on email and Excel.

1. **Internal rules (P1).** The 5 policy documents are short, but few people read them. HR spends about 2 hours a week answering the same questions (leave, expenses, laptops, purchases). Answers that link back to the policy save that time and point people to the actual rule.
2. **Past projects (P9).** About 900 numbered projects sit on a file server, but the knowledge of *what* was built is in people's heads. "Have we designed a footbridge like this before?" goes unanswered, and work that could be reused is done again from scratch.

Both problems have the same shape: a question in plain language, a small set of documents, and an answer people can trust because it shows where it came from. That's why I solved them in one app.

## For whom

- **All staff** (engineers, project managers, office staff): quick answers about company rules, without reading the policies or emailing HR. No training needed: one page, example questions, plain language.
- **Engineers and project managers** starting a bid or a design: find similar past projects, who led them, and where the files are.
- **HR**: a dashboard showing what people ask, which questions the policies don't answer, and which answers were rated 👎, i.e. where a policy is missing or unclear.

## What it does

| | |
|---|---|
| **Ask about company rules** | Searches the 5 policies (one chunk per `##` section). With AI: a short answer (max 4 sentences) with citations like `[leave.md › Annual leave]`. Without AI: the matching policy section, word for word. |
| **Never invents** | If no section really matches, it says *"I couldn't find this in the Corvalis policies. Please ask HR (hr@corvalis.be)."* The AI may only use the sections it is given, and citations are checked against them. |
| **Sources** | Every answer has a collapsible list of the sections it is based on. |
| **Find past projects** | Same search over 60 sample projects (type, materials, city, summary), with optional type / year filters. Results are cards with number, year, city, project manager, materials, client, budget and the folder path (one-click copy). With AI, a one-line "why it matches" per project. |
| **Feedback** | 👍 / 👎 on every answer. |
| **HR dashboard** (`/hr`) | Number of questions, % answered, top 10 questions, unanswered questions (grouped, most frequent first), 👎-rated answers. |
| **Persistence** | Everything is in one SQLite file (`backend/corvalis.db`): policy chunks, projects, every question with its answer and rating. It survives restarts. |

### How an answer is built

```
question ──► BM25 keyword search ──► relevant enough? ──no──► "I couldn't find this… ask HR"
                                          │ yes
                                          ▼
                                 Ollama available? ──no──► show best section / project cards
                                          │ yes                     (mode: "search")
                                          ▼
                          local model writes a short answer
                          from those sources only, citations checked   (mode: "ai")
                          (on timeout or error → search mode)
```

"Relevant enough" means **both**: a minimum BM25 score, and the best section must contain at least 60% of the question's keywords (50% for projects). The score alone wasn't enough: "parental leave" scored higher than some correct matches because of the word "leave". See `backend/app/search.py`.

## How to run

You need **Python 3.11+** and **Node.js 20+**. Two terminals:

**1. Backend** (API on http://127.0.0.1:8000)

```
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app
```

On the first start, it creates `backend/corvalis.db` and loads the policies and the 60 sample projects.

**2. Frontend** (http://localhost:5173)

```
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. That's it: the app works fully without AI.

**Tests:** `cd backend` then `pytest` (70 tests, no Ollama needed).

**Reset the demo data:** stop the backend and delete `backend/corvalis.db`. It is recreated on the next start.

### Optional: local AI model (Ollama)

With Ollama running, answers are short sentences written from the sources instead of the raw section. Nothing to configure: the backend detects it (checked every 30 s).

1. Install Ollama. Check with `ollama --version`. If it's missing:
   - Windows: `winget install Ollama.Ollama` (or https://ollama.com/download)
   - macOS: `brew install ollama`
   - Linux: `curl -fsSL https://ollama.com/install.sh | sh`
2. Pull a small model: `ollama pull llama3.2:3b` (~2 GB).
   On a slow or low-RAM machine, use `ollama pull qwen2.5:1.5b` (~1 GB) and set `OLLAMA_MODEL=qwen2.5:1.5b` before starting the backend.
3. Verify: `ollama run llama3.2:3b "Say hi in 3 words"` replies, and http://localhost:11434/api/tags lists the model.

Settings (environment variables, all optional): `OLLAMA_MODEL` (default `llama3.2:3b`), `OLLAMA_URL` (default `http://127.0.0.1:11434`), `CORVALIS_DB` (database file path).

### Troubleshooting

- **The page doesn't update after editing code, or the backend doesn't reload:** file watching is unreliable in OneDrive/synced folders. Restart `npm run dev` / `uvicorn`, or clone the repo outside OneDrive.
- **"Can't reach the Ask Corvalis server":** the backend isn't running on port 8000.
- **Answers say "Search result (AI offline)":** Ollama isn't running or the model isn't pulled. This is expected and the app still works.

## What works

- Both use cases end to end: web UI → FastAPI → SQLite → optional local AI, with the data kept after a restart.
- Tested by hand with Ollama on and off: about 25 real-sounding rule questions across all 5 policies, plus off-topic ones ("pizza recipe", "parental leave", "company car policy" → "ask HR"). With Ollama on, an answer takes about 1 s (llama3.2:3b, after the first one, which loads the model).
- Safety nets for the small model:
  - wrong document names in citations are corrected, and citations to sections it wasn't given are removed;
  - for projects, the model only picks *which* projects match and *why*; the number, year and project manager always come from the database (in testing, the 3B model made up project managers);
  - AI errors or timeouts (30 s) fall back to search mode.
- Error states in the UI: server unreachable, validation (empty or >500 characters), unexpected error, slow AI ("Still working…"), and "Try again" in place.
- Works at phone width.
- 70 automated tests: search quality on the real policies, the relevance rule, ingestion and restart, the API with AI faked on, off and failing, project search and filters, HR stats.

## What's missing (left out on purpose)

- **Login / SSO and access rights.** Anyone who can open the page can see the HR dashboard. In reality: company SSO (Microsoft 365), with `/hr` restricted to HR.
- **Real file-server indexing.** The 60 projects are realistic but generated (fixed seed). The real ~900 projects would need a crawler over `\\fileserver\projects` (project sheets, reports), which needs access and data cleaning.
- **French / Dutch.** The policies and the search are English only. A Belgian company needs FR/NL (questions *and* documents).
- **Synonyms.** Keyword search misses questions worded differently from the policy: "dinner" vs "evening meal", "doctor's note" vs "medical certificate". They safely get "ask HR" rather than a wrong answer, but they are misses.
- **Teams / Outlook integration.** That's where staff actually ask questions.
- **An admin page to edit policies.** Policies are files in `docs/`; changing them means deleting the database so they are reloaded.
- **Conversation memory.** Each question is answered on its own; follow-ups ("and for part-time?") don't use the previous question.

## Next steps

1. **Pilot with HR for 2–3 weeks**, then use the dashboard (unanswered + 👎) to fix or complete the policies. That is the quickest real-world win.
2. **Hybrid search**: add embeddings (e.g. a small local multilingual embedding model via Ollama) next to BM25, to catch synonyms and FR/NL questions.
3. **Index the real project server**: start from each project's sheet or final report, extract type, materials, client, PM and summary, and keep the folder path.
4. **SSO + roles**, then a **Teams bot** using the same API.
5. Re-load the policies automatically when a file in `docs/` changes (instead of deleting the database).

## How I used AI

I built this with an AI coding assistant (Claude Code), working phase by phase from a written build plan: setup → policy search → answer API → chat UI → HR dashboard → past projects → finishing. After each phase I ran it, checked it in the browser, and committed.

The AI wrote most of the code. I set the scope, the stack and the priorities (company rules fully working before past projects; small and solid over big), and reviewed the results. Testing with real questions found problems that the first version missed, and they were fixed along the way:

- A score threshold alone let "parental leave" match the sick-leave section → added the keyword-coverage rule.
- The 3B model cited the wrong file, and invented project managers for past projects → citations are checked in code, and project facts come from the database.
- Every call to `localhost` took 2.4 s on Windows (IPv6 lookup first) → use `127.0.0.1`.
- Weak extra sources cluttered answers ("Approved suppliers" for a lost laptop) → only sources scoring at least half of the best one are shown.

*(Draft: rewrite this section in your own words.)*

## Project layout

```
backend/
  app/main.py           API endpoints + answer pipeline
  app/search.py         tokenizer, BM25 index, "relevant enough" rule
  app/llm.py            Ollama client, prompts, citation / project-line checks
  app/ingest.py         docs/*.md → one chunk per "##" section
  app/seed_projects.py  60 sample projects (fixed seed)
  app/db.py             SQLite schema (chunks, projects, questions)
  tests/                pytest
frontend/src/
  Chat.tsx              the two tabs: company rules / past projects
  Answer.tsx            answer, badge, sources, 👍/👎
  ProjectCard.tsx       one past project
  HrDashboard.tsx       /hr page
  api.ts                calls to the backend
docs/                   the 5 policy files (unchanged)
```
