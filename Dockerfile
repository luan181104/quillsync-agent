FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# state.json persists between runs if you mount a volume to /app/state.json
# (otherwise each run starts "fresh" and will treat every article as new)
ENV ARTICLES_DIR=/app/articles
ENV STATE_FILE=/app/state.json

RUN mkdir -p /app/articles

# Single run, then exit 0 — matches: docker run -e OPENAI_API_KEY=... image
CMD ["python", "main.py"]
