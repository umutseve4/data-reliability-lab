FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .
COPY data ./data
USER 65532:65532
ENTRYPOINT ["reliability-lab"]
CMD ["run", "--source", "data/events.jsonl", "--db", "/tmp/lab.db"]
