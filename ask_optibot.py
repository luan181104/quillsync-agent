"""
ask_optibot.py
Sanity-check script — the Gemini equivalent of "test in the OpenAI
Playground". Asks OptiBot a question, grounded in the File Search
store, and prints the answer plus the cited source URLs.

Usage:
  python ask_optibot.py "How do I add a YouTube video?"
"""
import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""


def ask(question: str) -> None:
    api_key = os.environ["GEMINI_API_KEY"]
    store_name = os.environ["GEMINI_FILE_SEARCH_STORE_NAME"]
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store_name]))],
        ),
    )

    print(f"Q: {question}\n")
    print(response.text)

    # Print cited source URLs, if the SDK surfaced grounding metadata
    try:
        chunks = response.candidates[0].grounding_metadata.grounding_chunks
        if chunks:
            print("\n--- Cited sources ---")
            for c in chunks[:3]:
                title = getattr(c.retrieved_context, "title", None) if hasattr(c, "retrieved_context") else None
                uri = getattr(c.retrieved_context, "uri", None) if hasattr(c, "retrieved_context") else None
                print(f"- {title or uri}")
    except (AttributeError, IndexError, TypeError):
        pass


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "How do I add a YouTube video?"
    ask(q)
