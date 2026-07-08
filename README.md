# QuillSync Agent — OptiBot Mini-Clone (Google Gemini edition)

Scrapes `support.optisigns.com` (Zendesk Help Center API) → clean Markdown →
uploads the delta to a **Google Gemini File Search store** → Gemini
(`gemini-2.5-flash` + the File Search tool) answers support questions with
cited article URLs. Runs as a one-shot Docker job you schedule daily.

## Architecture

```
scraper.py               -> pulls all published articles via Zendesk Help Center API
converter.py              -> HTML -> clean Markdown (+ front-matter, content hash)
state_store.py             -> state.json: article_id -> {hash, document_name, ...}
vector_store_manager.py -> upload/delete Documents in a Gemini File Search store
create_assistant.py     -> ONE-TIME: creates the File Search store
ask_optibot.py            -> sanity-check script (asks a question, prints citations)
main.py                    -> daily job: scrape -> diff -> upload delta -> log
```

## Why Gemini File Search (not a custom vector DB)

Gemini's File Search Tool is a fully managed RAG system: you upload a file,
Google handles chunking, embedding, indexing and retrieval server-side, and
you query it directly inside a normal `generateContent` call via the
`file_search` tool. This removes the need to run/host a vector database.
Storage and query-time embeddings are free; you're only charged a small,
fixed rate for the initial indexing embedding pass.

## Chunking strategy

Uploaded Markdown files use Gemini's **default automatic chunking**. Each
file is one focused help article (typically 200–1500 words), so the
default splitter already produces coherent, well-bounded chunks without
any custom pre-splitting on my side. `main.py` logs a rough chunk-count
estimate per run (`chunks_est`). A custom `chunking_config` (max tokens per
chunk / overlap) is also available if finer control is ever needed.

## Delta detection

Each article's Markdown body is SHA-256 hashed and stored in `state.json`
alongside the Gemini `document_name` it was imported as. On every run:

- **new article_id** → `ADDED`
- **known article_id, hash changed** → old Document deleted from the
  store, new file uploaded → `UPDATED`
- **known article_id, hash unchanged** → `SKIPPED`
- **article_id no longer returned by Zendesk** → old Document removed →
  `REMOVED`

Only added/updated files are re-uploaded — that's the "delta".

## Setup

```bash
git clone <your-repo-url>
cd quillsync-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.sample .env
```

Get a free API key at **aistudio.google.com → Get API key** (no credit card
required) and put it in `.env` as `GEMINI_API_KEY`.

### One-time: create the File Search store

```bash
python create_assistant.py
```

Copy the printed `GEMINI_FILE_SEARCH_STORE_NAME` into `.env` (and into your
hosting platform's secret manager) so every future run reuses the same
knowledge base instead of creating a new store each time.

## Run locally

```bash
python main.py
```

Logs added / updated / skipped / removed counts, e.g.:

```
=== QuillSync run finished: added=100 updated=0 skipped=0 removed=0 chunks_est=853 file_search_store=fileSearchStores/xxxx ===
```

## Sanity check (equivalent of testing in the OpenAI Playground)

```bash
python ask_optibot.py "How do I add a YouTube video?"
```

Expected: an answer in ≤5 bullets citing up to 3 `Article URL:` lines.
Take a screenshot of the terminal output showing this and save it as
`screenshot-assistant-answer.png` in the repo root.

## Run in Docker (single run, exits 0)

```bash
docker build -t quillsync-agent .
docker run --rm \
  -e GEMINI_API_KEY=... \
  -e GEMINI_FILE_SEARCH_STORE_NAME=fileSearchStores/xxxx \
  -v $(pwd)/state.json:/app/state.json \
  quillsync-agent
```

Mounting `state.json` is what lets the delta logic persist across runs.

## Scheduling the daily job

Deployed as a **GitHub Actions scheduled workflow** (free, no credit card,
no third-party host needed — see `.github/workflows/daily-sync.yml`):

1. Push this repo to GitHub.
2. Repo → **Settings → Secrets and variables → Actions** → add two
   repository secrets: `GEMINI_API_KEY` and `GEMINI_FILE_SEARCH_STORE_NAME`.
3. Repo → **Settings → Actions → General → Workflow permissions** → select
   **"Read and write permissions"** (needed so the job can commit the
   updated `state.json` / `articles/` back to the repo after each run).
4. The workflow runs automatically every day at 03:00 UTC
   (`cron: "0 3 * * *"`), and can also be triggered manually any time from
   the **Actions** tab → "Daily OptiSigns Sync" → **Run workflow**.

Since GitHub Actions runners are ephemeral (no persistent disk between
runs), the workflow's last step commits the updated `state.json` and
`articles/*.md` back to the repo — that's what makes delta-detection work
across runs, without needing a separate hosting platform or database.

**Job logs:** https://github.com/luan181104/quillsync-agent/actions/workflows/daily-sync.yml

## Notes / known limitations

- Zendesk's Help Center API already returns just the article body (no
  site nav/ads), so no extra HTML stripping was needed beyond a normal
  HTML→Markdown pass.
- This sandbox environment I authored the code in has an outbound
  network allowlist that blocks `support.optisigns.com` directly, so the
  scraper's HTTP logic was validated end-to-end by the person running
  this from their own machine (open internet access) rather than in the
  authoring sandbox.
- No API keys are hard-coded; everything is read from environment
  variables (`.env.sample` documents all of them).
- Originally prototyped against the OpenAI Assistants + Vector Store API;
  switched to Google Gemini's File Search Tool (this README) since it has
  a genuinely free tier with no payment method required.
