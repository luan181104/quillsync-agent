"""
create_assistant.py
Run this ONCE (locally) to create the Gemini File Search store that
will hold OptiBot's knowledge base. Gemini has no separate "Assistant"
resource like OpenAI's Assistants API — the persona/system prompt
below is instead passed as `system_instruction` at query time (see
ask_optibot.py). This script's only job is to create the store and
print the ID you must save.
"""
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Applied at query time (ask_optibot.py / main app), not stored server-side.
SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""


def main():
    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)

    store = client.file_search_stores.create(
        config={"display_name": "OptiBot Knowledge Base"}
    )
    print(f"Created File Search store: {store.name}")

    print("\nAdd this to your .env / hosting platform secrets:")
    print(f"GEMINI_FILE_SEARCH_STORE_NAME={store.name}")
    print("\n(System prompt below is reused by ask_optibot.py at query time — "
          "nothing to save for it, it's not a persisted resource in Gemini.)")
    print(SYSTEM_PROMPT)


if __name__ == "__main__":
    main()
