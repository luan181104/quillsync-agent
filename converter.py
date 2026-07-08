"""
converter.py
Converts a raw Zendesk article (HTML body) into a clean Markdown file
with a small YAML front-matter block, preserving headings, links and
code blocks. Zendesk's help_center API already returns just the article
body (no site nav/ads), so no extra stripping is required beyond
normal HTML->MD conversion.
"""
import re
import hashlib
from markdownify import markdownify as html_to_md
from slugify import slugify


def article_slug(article: dict) -> str:
    # Prefer the last path segment of the article's public URL,
    # fall back to a slugified title.
    html_url = article.get("html_url", "")
    tail = html_url.rstrip("/").split("/")[-1]
    tail = re.sub(r"^\d+-", "", tail)  # strip Zendesk's numeric id prefix
    return tail if tail else slugify(article["title"])


def to_markdown(article: dict) -> str:
    """Convert one Zendesk article object into a Markdown document (string)."""
    body_html = article.get("body") or ""
    body_md = html_to_md(
        body_html,
        heading_style="ATX",
        bullets="-",
        code_language="",
        strip=["script", "style"],
    ).strip()

    # collapse 3+ blank lines down to 2
    body_md = re.sub(r"\n{3,}", "\n\n", body_md)

    front_matter = (
        "---\n"
        f"title: \"{article['title'].replace(chr(34), chr(39))}\"\n"
        f"article_id: {article['id']}\n"
        f"source_url: {article['html_url']}\n"
        f"updated_at: {article['updated_at']}\n"
        "---\n\n"
    )

    return front_matter + f"# {article['title']}\n\nArticle URL: {article['html_url']}\n\n" + body_md + "\n"


def content_hash(markdown_text: str) -> str:
    """Stable hash used to detect whether an article actually changed."""
    return hashlib.sha256(markdown_text.encode("utf-8")).hexdigest()
