"""
main.py
Entry point for the daily sync job:
  1. Re-scrape all published articles from support.optisigns.com (Zendesk API)
  2. Convert each to clean Markdown
  3. Diff against local state.json (content hash) -> added / updated / skipped
  4. Upload only the delta to the Gemini File Search store
  5. Log counts and exit 0

Run locally:
  python main.py

Run in Docker (single run, exits 0):
  docker run --rm \
    -e GEMINI_API_KEY=... \
    -e GEMINI_FILE_SEARCH_STORE_NAME=fileSearchStores/xxx \
    -v $(pwd)/state.json:/app/state.json \
    quillsync-agent
"""
import os
import sys
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv

import scraper
import converter
import state_store
from vector_store_manager import VectorStoreManager

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not set. Aborting.")
        return 1

    articles_dir = os.getenv("ARTICLES_DIR", "articles")
    state_file = os.getenv("STATE_FILE", "state.json")
    max_articles = int(os.getenv("MAX_ARTICLES", "100"))
    vector_store_id = os.getenv("GEMINI_FILE_SEARCH_STORE_NAME") or None

    os.makedirs(articles_dir, exist_ok=True)

    logger.info("=== QuillSync run started: %s ===", datetime.now(timezone.utc).isoformat())

    # 1. Scrape
    articles = scraper.fetch_all_articles(max_articles=max_articles)
    if not articles:
        logger.error("No articles fetched — aborting so we don't wipe existing state.")
        return 1

    # 2. Convert
    state = state_store.load(state_file)
    vsm = VectorStoreManager(api_key=api_key, vector_store_id=vector_store_id)
    if not vector_store_id:
        logger.warning(
            "No GEMINI_FILE_SEARCH_STORE_NAME was set — created a NEW store (%s). "
            "Save this id so future runs reuse it!",
            vsm.vector_store_id,
        )

    added, updated, skipped, chunks_estimate = 0, 0, 0, 0

    seen_ids = set()
    for article in articles:
        article_id = str(article["id"])
        seen_ids.add(article_id)

        slug = converter.article_slug(article)
        md_text = converter.to_markdown(article)
        md_hash = converter.content_hash(md_text)
        filepath = os.path.join(articles_dir, f"{slug}.md")

        prev = state.get(article_id)

        if prev and prev.get("hash") == md_hash:
            skipped += 1
            continue

        # write/overwrite the markdown file on disk
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_text)

        # if this article already had a document in the store, remove the old version first
        if prev and prev.get("document_name"):
            vsm.remove_file(prev["document_name"])

        # display_name must be unique per article so we can look it back up
        display_name = f"{article_id}-{slug}"[:512]
        document_name = vsm.upload_and_attach(filepath, display_name)
        # rough chunk estimate: ~800 chars per chunk (Gemini's default chunking)
        chunks_estimate += max(1, len(md_text) // 800 + 1)

        state[article_id] = {
            "hash": md_hash,
            "document_name": document_name,
            "path": filepath,
            "slug": slug,
            "source_url": article["html_url"],
            "updated_at": article["updated_at"],
        }

        if prev:
            updated += 1
            logger.info("UPDATED  %s (%s)", slug, article["html_url"])
        else:
            added += 1
            logger.info("ADDED    %s (%s)", slug, article["html_url"])

    # (optional) handle articles that disappeared from the Help Center since last run
    removed_ids = set(state.keys()) - seen_ids
    for rid in removed_ids:
        entry = state.pop(rid, None)
        if entry and entry.get("document_name"):
            vsm.remove_file(entry["document_name"])
            logger.info("REMOVED  %s (no longer published)", entry.get("slug", rid))

    state_store.save(state_file, state)

    logger.info(
        "=== QuillSync run finished: added=%d updated=%d skipped=%d removed=%d chunks_est=%d file_search_store=%s ===",
        added, updated, skipped, len(removed_ids), chunks_estimate, vsm.vector_store_id,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
