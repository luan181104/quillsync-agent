"""
scraper.py
Pulls every published article from a Zendesk-powered Help Center
(support.optisigns.com) via the public Zendesk Help Center API.

Docs: https://developer.zendesk.com/api-reference/help_center/help-center-api/articles/
"""
import os
import time
import logging
import requests

logger = logging.getLogger("scraper")

ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN", "support.optisigns.com")
ZENDESK_LOCALE = os.getenv("ZENDESK_LOCALE", "en-us")
BASE_URL = f"https://{ZENDESK_SUBDOMAIN}/api/v2/help_center/{ZENDESK_LOCALE}/articles.json"

PAGE_SIZE = 100


def fetch_all_articles(max_articles: int = 1000) -> list[dict]:
    """
    Paginates through the Zendesk Help Center API and returns a list of
    article dicts (raw API objects) for every published article.
    """
    articles = []
    url = f"{BASE_URL}?per_page={PAGE_SIZE}&sort_by=updated_at&sort_order=desc"

    while url and len(articles) < max_articles:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for a in data.get("articles", []):
            if a.get("draft"):
                continue  # skip unpublished drafts
            articles.append(a)

        url = data.get("next_page")
        # be polite to the API
        if url:
            time.sleep(0.3)

    logger.info("Fetched %d published articles from Zendesk", len(articles))
    return articles[:max_articles]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    arts = fetch_all_articles(max_articles=30)
    for a in arts[:5]:
        print(a["id"], a["title"], a["html_url"])
    print(f"... total fetched: {len(arts)}")
