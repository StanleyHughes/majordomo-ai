# Majordomo: AI Voice Assistant

Majordomo ("Domo" for short) is a personal AI assistant you talk to by voice, in the
manner of a classic head butler: dry, witty and quietly competent. You tap a button,
speak, and Domo answers out loud in about a second. You can interrupt it mid-sentence,
or type instead of talking.

It's built on [LiveKit](https://livekit.io) for real-time audio and Google's
[Gemini Live](https://ai.google.dev/gemini-api/docs/live) model for speech and
conversation. Everything runs in Docker, so one command starts it.

> **Status: phase 1 (foundation).** Voice conversation, typed messages, live transcript
> and a configurable persona work. Web search, weather, camera, memory, reminders,
> calendar, email and proper sign-in come in later phases. See
> [docs/requirements.md](docs/requirements.md) for the full plan.

## Two ways to run it

| | **Personal mode** | **Hosted mode** |
|---|---|---|
| Who it's for | You, on your own machine | A shared instance for people you invite |
| Sign-in | None | Access code now; Google/Microsoft sign-in in phase 2 |
| Keys | Your own | The host's (paid keys, with spending caps) |
| HTTPS | Not needed on `localhost` | Required, set up automatically |
| Typical machine | Laptop, Mac, ASUS GX10 | A cloud server with a domain name |

Both use the same code. `MAJORDOMO_MODE` in `.env` picks one.

## What's inside

```
agent/      Python voice agent (LiveKit Agents + Gemini Live) and Domo's persona
backend/    Small FastAPI service that hands the browser a short-lived LiveKit token
web/        Tap-to-talk web app, served by Caddy (which also handles HTTPS)
docs/       Requirements and security notes
```

How a conversation works: the web app asks the backend for a token, joins a fresh
LiveKit room, and LiveKit sends the agent into the same room. Your voice goes to
LiveKit, the agent passes it to Gemini, and Gemini's reply comes back the same way.
The browser never sees any API keys.

## Getting your keys

You need two free accounts. Each takes about five minutes.

### 1. LiveKit Cloud (real-time audio)

1. Sign up at [cloud.livekit.io](https://cloud.livekit.io) and create a project
   (any name, e.g. "majordomo").
2. Open **Settings → API Keys** and create a key.
3. Copy three values into `.env`:
   - **WebSocket URL**, starting with `wss://` → `LIVEKIT_URL`
   - **API Key** → `LIVEKIT_API_KEY`
   - **API Secret** → `LIVEKIT_API_SECRET` (shown only once; copy it now)

The free plan is plenty for personal use.

### 2. Google Gemini (the voice and brain)

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in
   with a Google account.
2. Click **Create API key** and copy it into `.env` as `GOOGLE_API_KEY`.

The free tier is fine for testing on your own. Before other people use a hosted
instance, switch to a paid key and set a spending cap (see
[docs/security.md](docs/security.md#sec-3-spending-caps-before-anyone-else-uses-it)),
because free-tier conversations may be used by Google to improve its products.

## Personal mode setup

You need [Docker](https://docs.docker.com/get-docker/) (Docker Desktop on a Mac;
Docker Engine on Linux, which DGX OS on the GX10 already includes).

```bash
git clone https://github.com/StanleyHughes/majordomo-ai.git
cd majordomo-ai
cp .env.example .env
# Open .env and paste in your LiveKit and Gemini keys.
# Optional: set MAJORDOMO_USER_ADDRESS=Stan (or Sir, Doctor, or leave it blank).
docker compose up -d --build
```

Open **http://localhost:8080**, tap the button, allow the microphone, and say hello.

To update to the latest version later:

```bash
git pull
docker compose up -d --build
```

Useful commands:

```bash
docker compose logs -f agent   # watch what Domo is doing
docker compose restart agent   # after changing persona settings in .env
docker compose down            # stop everything
```

### Using it from your phone or another computer

Phones only allow the microphone over HTTPS, so `http://<your-ip>:8080` won't work.
The easiest way is a free [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/):

```bash
# On the machine running Majordomo (e.g. the GX10):
cloudflared tunnel --url http://localhost:8080
```

That prints an `https://...trycloudflare.com` address you can open on your phone. For a
permanent address on your own domain, create a named tunnel in the Cloudflare dashboard
and point it at `http://localhost:8080`. No ports need to be opened on your router.

> Anyone who knows a tunnel address can use your keys. For anything longer than a quick
> test, use hosted mode settings (`MAJORDOMO_MODE=hosted` with an access code) even
> behind a tunnel.

## Hosted mode setup

For a cloud server with a public address and a domain name (e.g. `domo.example.com`).

1. Point the domain's DNS **A record** at the server's IP address.
2. Open ports **80** and **443** in the server's firewall.
3. Install Docker, clone the repo and create `.env` as above, then set:

   ```bash
   MAJORDOMO_MODE=hosted
   SITE_ADDRESS=domo.example.com
   # A long random code you give to the people you invite:
   MAJORDOMO_ACCESS_CODE=<output of: python3 -c "import secrets; print(secrets.token_urlsafe(24))">
   ```

4. Use paid Gemini and LiveKit plans with spending caps set (SEC-3, in
   [docs/security.md](docs/security.md)).
5. Start it with the hosted override, which publishes ports 80 and 443:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.hosted.yml up -d --build
   ```

Caddy fetches an HTTPS certificate automatically and redirects plain HTTP to HTTPS.
Open `https://domo.example.com`, enter the access code, and tap to talk.

**Hosted mode behind Cloudflare Tunnel** (e.g. on the GX10 instead of a cloud server):
keep `SITE_ADDRESS=:80`, set `MAJORDOMO_MODE=hosted` and an access code, start with the
plain `docker compose up -d`, and point the tunnel at `http://localhost:8080`. Cloudflare
provides HTTPS.

## Settings

All settings live in `.env`. The main ones:

| Setting | What it does |
|---|---|
| `MAJORDOMO_MODE` | `personal` or `hosted` |
| `MAJORDOMO_USER_ADDRESS` | How Domo addresses you: a name, a title, or blank for nothing |
| `GEMINI_VOICE` | Voice name, e.g. `Charon` (default), `Puck`, `Kore`, `Fenrir`, `Aoede` |
| `GEMINI_MODEL` | Gemini Live model; blank uses the default in `agent/majordomo_agent/config.py` |
| `MAJORDOMO_PERSONA_EXTRA` | Extra instructions appended to Domo's persona |
| `MAJORDOMO_SILENCE_MS` | How long a pause means you've finished speaking, default 600 |
| `MAJORDOMO_MAX_SESSION_MINUTES` | Ends a conversation after this long (cost guard), default 60 |
| `TOKEN_TTL_SECONDS` | How long a join token is valid, default 600 |
| `MAJORDOMO_ACCESS_CODE` | Hosted mode: the code visitors must enter |
| `WEB_PORT`, `SITE_ADDRESS` | Where the web app listens |

Domo's personality is in [`agent/majordomo_agent/persona.py`](agent/majordomo_agent/persona.py).

Long conversations are kept alive with Gemini's **session resumption** (reconnects
seamlessly if the Gemini connection drops or hits its time limit) and **context window
compression** (trims the oldest turns instead of ending the session).

## Multi-arch images

Every image builds for both **arm64** (ASUS GX10, Apple Silicon) and **amd64** (typical
cloud servers). `docker compose up --build` builds for the machine you're on. To build
both at once and push them to a registry:

```bash
docker buildx create --use --name domo   # once
docker buildx bake --push                 # uses docker-bake.hcl
```

CI does this automatically on every push to `main`, publishing to
`ghcr.io/stanleyhughes/majordomo-{agent,backend,web}`. To run the published images
instead of building, use `docker compose pull && docker compose up -d`.

## Development without Docker

```bash
# Agent (Python 3.12+)
cd agent && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r ../requirements-dev.txt
python -m majordomo_agent.main dev   # reads ../.env

# Backend
cd backend && pip install -r requirements.txt
uvicorn app.server:app --reload --port 8000

# Web (proxies /api to localhost:8000)
cd web && npm install && npm run dev
```

Tests: `pytest` in `agent/` and `backend/`. Lint: `ruff check .` from the repo root.

## Security

Phase 1 covers rules SEC-1 to SEC-4: secrets never committed, browser gets only short-lived
tokens, spending caps, and HTTPS everywhere. Details and the one-time steps you need to do
(including turning on GitHub secret scanning and push protection) are in
[docs/security.md](docs/security.md).

## License

Copyright 2026 Stanley Hughes. Licensed under the [Apache License 2.0](LICENSE).
