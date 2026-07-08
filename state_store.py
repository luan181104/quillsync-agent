"""
state_store.py
Tiny JSON-file "database" that remembers, per article:
  - the content hash we last uploaded
  - the OpenAI file_id currently attached to the vector store
This is how the daily job knows what's new / updated / unchanged,
and which old file to remove from the vector store on update.
"""
import json
import os
from threading import Lock

_lock = Lock()


def load(state_file: str) -> dict:
    if not os.path.exists(state_file):
        return {}
    with open(state_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save(state_file: str, state: dict) -> None:
    with _lock:
        tmp = state_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, state_file)
