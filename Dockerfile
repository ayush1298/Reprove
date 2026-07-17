FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY reprove ./reprove
RUN pip install --no-cache-dir .

ENTRYPOINT ["reprove"]
