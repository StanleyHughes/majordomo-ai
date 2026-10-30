# Majordomo voice agent. Multi-arch: python:3.12-slim ships amd64 and arm64,
# and the LiveKit and Google wheels used here are published for both.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY majordomo_agent ./majordomo_agent

RUN useradd --system --create-home --uid 10001 domo
USER domo

# The agent only makes outbound connections to LiveKit and Gemini.
# No ports need to be opened on the host.
CMD ["python", "-m", "majordomo_agent.main", "start"]
