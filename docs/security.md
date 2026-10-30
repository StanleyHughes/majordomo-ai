# Security (phase 1)

Majordomo's requirements list seven security rules (see `requirements.md`, section 5a).
Phase 1 covers SEC-1 to SEC-4. This page says how each one is met and what you need to
do yourself.

## SEC-1: Secrets stay out of git

**In the code**
- All keys live in `.env`, which `.gitignore` excludes (along with `.env.*`, `*.pem`, `*.key`).
  Only `.env.example`, with blank values, is committed.
- Every push and pull request runs [gitleaks](https://github.com/gitleaks/gitleaks) in CI
  (`.github/workflows/ci.yml`) and fails if anything that looks like a key is found.
- Each container only receives the settings it needs (`docker-compose.yml`). The web
  container receives no keys at all.

**You do this once on GitHub** (Settings → Code security):
1. Turn on **Secret scanning**.
2. Turn on **Push protection**, so GitHub blocks a push that contains a key.

If a key is ever committed by mistake, treat it as leaked: revoke it in the provider's
console first, then remove it from the repo.

## SEC-2: The browser gets tokens, never keys

- The web app asks the backend (`POST /api/token`) for a LiveKit access token.
- The token is signed with your LiveKit secret on the server and is limited to:
  - **one room**, created fresh for each conversation,
  - **a short lifetime** (`TOKEN_TTL_SECONDS`, default 10 minutes, clamped to 1 to 60
    minutes). The token is only needed to join; the call itself carries on after it expires.
- The Gemini key is only given to the agent container, which talks to Gemini directly.
  The browser never talks to Gemini.
- The backend is not published on the host. Only the web container can reach it.
- Token requests are rate limited (10 per minute per visitor).
- In hosted mode, visitors need an access code (`MAJORDOMO_ACCESS_CODE`) until proper
  invite-only sign-in arrives in phase 2. The backend refuses to start in hosted mode
  without one.

## SEC-3: Spending caps before anyone else uses it

Do this **before** anyone other than you uses a hosted instance.

**Google (Gemini)**
1. In [Google AI Studio](https://aistudio.google.com), open your key's project in
   Google Cloud Console → **Billing → Budgets & alerts**.
2. Create a budget (for example $20 a month) with email alerts at 50%, 90% and 100%.
3. A budget alone only alerts; to make it a hard stop, either set a lower quota under
   **APIs & Services → Generative Language API → Quotas**, or follow Google's guide to
   [disable billing automatically when a budget is hit](https://cloud.google.com/billing/docs/how-to/disable-billing-with-notifications).
4. Use a paid key for other people's conversations: free-tier content can be used by
   Google to improve its products (NFR-4).

**LiveKit Cloud**
1. In [LiveKit Cloud](https://cloud.livekit.io) → **Settings → Billing**, stay on the free
   plan while testing, or set a spending limit on a paid plan.
2. Turn on usage alerts.

**In Majordomo itself**
- `MAJORDOMO_MAX_SESSION_MINUTES` (default 60) ends any single conversation after that long.
- Rooms close a minute after everyone leaves, so nothing keeps running unattended.
- Per-user limits and a monthly cap inside Majordomo come in phase 4 (FR-53, NFR-3).

## SEC-4: HTTPS everywhere

- **LiveKit**: LiveKit Cloud URLs are `wss://` (TLS). In hosted mode the backend refuses
  to start if `LIVEKIT_URL` is not `wss://`.
- **Hosted mode on a server with a domain**: set `SITE_ADDRESS=your.domain` and start with
  `docker-compose.hosted.yml`. Caddy gets a free certificate from Let's Encrypt, renews it,
  and redirects HTTP to HTTPS. HSTS is sent on every HTTPS response.
- **Behind Cloudflare Tunnel** (e.g. the GX10): Cloudflare provides the HTTPS certificate;
  keep `SITE_ADDRESS=:80` and point the tunnel at `http://localhost:8080`. Caddy trusts
  the tunnel's `X-Forwarded-Proto` header because the tunnel runs on a private network.
- **The backend checks**: in hosted mode, it refuses to issue a token for a request that
  did not arrive over HTTPS.
- **Personal mode on your own machine**: `http://localhost` is fine. Browsers allow the
  microphone on `localhost` without HTTPS. To use it from your phone, use a tunnel or the
  hosted setup, because phones only allow the microphone over HTTPS.
