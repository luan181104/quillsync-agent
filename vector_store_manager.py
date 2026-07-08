"""
vector_store_manager.py
Thin wrapper around Google Gemini's File Search Tool (a fully managed
RAG system: chunking + embeddings + vector search are all handled by
Google's backend).
Docs: https://ai.google.dev/gemini-api/docs/file-search

Keeps the SAME public interface as the original OpenAI version
(create/upload_and_attach/remove_file/file_counts) so main.py barely
had to change when we switched providers.
"""
import logging
import time
from google import genai

logger = logging.getLogger("vector_store_manager")


class VectorStoreManager:
    def __init__(self, api_key: str, vector_store_id: str | None = None, name: str = "OptiBot Knowledge Base"):
        self.client = genai.Client(api_key=api_key)
        self.vector_store_id = vector_store_id or self._create_store(name)

    def _create_store(self, name: str) -> str:
        store = self.client.file_search_stores.create(config={"display_name": name})
        logger.info("Created new File Search store: %s", store.name)
        return store.name  # e.g. "fileSearchStores/abc123"

    def _wait(self, operation):
        """Polls a Gemini long-running operation until it's done."""
        while not operation.done:
            time.sleep(2)
            operation = self.client.operations.get(operation)
        return operation

    def upload_and_attach(self, filepath: str, display_name: str) -> str | None:
        """Uploads + imports one markdown file into the File Search store.
        `display_name` must be unique per article (we use '<article_id>-<slug>')
        so we can look the Document back up afterwards.
        Returns the Document resource name (needed later to delete on update)."""
        operation = self.client.file_search_stores.upload_to_file_search_store(
    file=filepath,
    file_search_store_name=self.vector_store_id,
    config={"display_name": display_name, "mime_type": "text/markdown"},
)
        self._wait(operation)
        return self._find_document_name(display_name)

    def _find_document_name(self, display_name: str) -> str | None:
        pager = self.client.file_search_stores.documents.list(parent=self.vector_store_id)
        for doc in pager:
            if doc.display_name == display_name:
                return doc.name
        return None

    def remove_file(self, document_name: str) -> None:
        """Deletes an old Document (used when an article is updated/removed)."""
        if not document_name:
            return
        try:
            self.client.file_search_stores.documents.delete(
                name=document_name, config={"force": True}
            )
        except Exception as e:
            logger.warning("Could not delete document %s: %s", document_name, e)

    def file_counts(self) -> dict:
        """Basic stats about the store (Gemini's API is lighter here than
        OpenAI's — it doesn't expose a live chunk/file counter, so we just
        confirm the store still exists)."""
        store = self.client.file_search_stores.get(name=self.vector_store_id)
        return {"vector_store_id": store.name}
