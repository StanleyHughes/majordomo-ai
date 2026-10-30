# Majordomo: AI Voice Assistant Requirements

- **Status:** v1.3 (2026-10-30). All open questions answered; security section added; product named Majordomo; deployment targets added; ready for v1 planning.
- **Owner:** Stan
- **Reference:** `../SupportData/DavidNguyenJARVIS/video-notes.md` (David Nguyen's LiveKit + Gemini JARVIS tutorial)

All open questions have been answered. Decisions are recorded where they apply and summarized in section 10.

---

## 1. Purpose and vision

Build Majordomo ("Domo" for short), a personal AI assistant inspired by JARVIS, that you talk to naturally by voice (or type to), that can see through a camera, look things up, and take actions on your behalf. It should be usable by Stan first, and then by other people who want an AI assistant, without them needing to be developers.

### Goals
1. Natural, low-latency, interruptible voice conversation.
2. Useful tools out of the box: web search, weather, browser control, camera vision.
3. Available on web, iPhone and Android.
4. Easy for a non-technical person to set up and use.
5. Low or zero running cost for personal use (free tiers where possible).

### Non-goals (for v1)
- Smart-home / IoT control (candidate for a later phase).
- Training custom models.
- Enterprise multi-tenant administration.

## 2. Users

| Persona | Description | Key needs |
|---|---|---|
| Owner (Stan) | Builds and runs the system, power user | Full tool access, easy customization of personality and tools |
| Invited user | Friend/family/colleague given access | Simple sign-in, works on their phone, private conversations |
| Self-hoster | Technical person who clones the project | Clear setup docs, uses own API keys |

**Decided (2026-10-28): both.** Stan hosts a shared instance for invited users, and anyone can also install their own copy. This means:
- One codebase with two modes: **hosted mode** (sign-in, multiple users, usage limits, Stan's paid keys) and **personal mode** (one user, no sign-in, runs on their own machine with their own keys).
- The project is published as open source on GitHub under the Apache 2.0 license, with a setup guide and a one-command install (e.g. Docker Compose).
- Self-installed copies never depend on Stan's server or keys.
- The hosted instance needs a short privacy notice and terms of use, since other people's voice and video pass through it.

## 3. Architecture

Keep the tutorial's core stack, and add the pieces a single-user demo leaves out.

- **Real-time transport:** LiveKit Cloud as the media server now, using the LiveKit Agents framework (Python); a self-hosted LiveKit server is a later option. Switching is a config change (LiveKit URL, API key and secret). Cloud-only extras (enhanced noise cancellation, agent hosting, analytics) stay optional, so nothing depends on them. Turn detection enabled.
- **Deployment:** the agent worker, backend and web app each run as a Docker container. Personal installs start everything with `docker compose up`. Docker does not affect voice quality, because audio flows through the LiveKit server, not the containers. A self-hosted LiveKit server needs host networking and open media ports.
- **Deployment targets:** the Docker containers run on either Stan's ASUS Ascent GX10 (NVIDIA GB10, ARM64, 128 GB unified memory, DGX OS) or Stan's cloud server. The cloud server is the recommended home for hosted mode, because it is always on and has a public address. The GX10 suits personal mode and development, and is the natural home for the local-model option (Ollama, Whisper) on its GPU. With LiveKit Cloud, the agent only makes outbound connections, so the GX10 needs no open ports; the backend and web app are exposed over HTTPS through a tunnel (e.g. Cloudflare Tunnel).
- **Model (default):** Google Gemini Live API for speech-in, speech-out and vision, with **session resumption** and **context window compression** turned on from day one. Without them, sessions end after about 15 minutes with audio only and about 2 minutes with the camera on.
- **Model (fallback):** a "pipeline" mode (separate speech-to-text, language model and text-to-speech) selectable by config, using Claude, so it can be used for harder tasks or if Gemini's pricing or free tier changes.
- **Tools:** Gemini's built-in Google Search, a weather function (Open-Meteo), and browser control through a Playwright MCP server. Other tools plug in as MCP servers.
- **Backend service:** sign-in, short-lived LiveKit token issuing, per-user storage, usage counting and logging. (The tutorial uses LiveKit's sandbox token server and has no accounts.)
- **Clients:** LiveKit web client (customized Majordomo UI), made installable on phones as a progressive web app (PWA). A Flutter app only if the PWA falls short.

**Decided (2026-10-28):** Gemini Live is the main model, because it is the only option with voice, camera vision and a free tier in one model. Claude, with separate speech-to-text and text-to-speech, is the backup mode for harder multi-step and tool-heavy tasks. OpenAI Realtime is the alternative if Gemini disappoints (similar quality, no free tier). A fully local option on Stan's Mac (Ollama with Gemma 3 or Qwen, Whisper, Kokoro or Piper) is possible later for private, offline use; it is slower and weaker at using tools. Gemini itself cannot run in Ollama.

## 4. Functional requirements

Priority: **M** = must (v1), **S** = should, **C** = could (later).

### 4.1 Conversation
| ID | Requirement | Pri |
|---|---|---|
| FR-1 | User can hold a real-time spoken conversation with the agent. | M |
| FR-2 | User can interrupt the agent mid-sentence (barge-in) and it stops and listens. | M |
| FR-3 | User can type messages instead of speaking; agent replies in text and/or voice. | M |
| FR-4 | A live transcript of both sides is shown in the client. | S |
| FR-5 | Agent has a configurable persona via a system prompt (default tone: dry and witty, in a classic butler style, as befits a majordomo, the head butler of a household). | M |
| FR-5a | Each user chooses how Majordomo addresses them: by name, by a title (e.g. "Sir", "Ma'am", "Doctor"), or nothing at all. Asked during first-time setup and changeable at any time. | M |
| FR-6 | Agent voice is selectable from the provider's voice list. | S |
| FR-7 | Wake word ("Hey Majordomo" or "Hey Domo") to start listening hands-free. Comes later with the Flutter app, or earlier on the Mac using openWakeWord. | C |
| FR-7a | In v1, a tap-to-talk button starts listening. | M |
| FR-8 | Supports multiple languages. | C |
| FR-9 | Conversations survive network drops and long sessions (including with the camera on) without the user noticing. | M |

**Decided (2026-10-28):** each user picks their own form of address (name, title, or nothing). The default tone is dry and witty.

### 4.2 Vision
| ID | Requirement | Pri |
|---|---|---|
| FR-10 | User can turn on the camera and ask questions about what it sees. | M |
| FR-11 | User can share their screen for the agent to see. | S |
| FR-12 | Camera/screen is off by default and clearly indicated when active. | M |

### 4.3 Tools
| ID | Requirement | Pri |
|---|---|---|
| FR-20 | Web search: agent answers with current information using Gemini's built-in Google Search, citing sources in the text view. A separate search provider (e.g. Tavily or Brave) is used only in pipeline mode. | M |
| FR-21 | Weather: current conditions and forecast for a named or current location, via Open-Meteo (free, no key). | M |
| FR-22 | Browser control: agent can open sites, navigate, click, fill forms and read pages, through a Playwright MCP server running on the owner's Mac. Turned off for invited users until a sandboxed cloud browser exists. | S |
| FR-23 | Actions with side effects (purchases, sending messages, submitting forms) require explicit spoken/typed confirmation. | M |
| FR-24 | Tools are pluggable: adding a new tool should not require changes to the core agent. MCP servers are the standard way to add tools. | S |
| FR-25 | Reminders and timers: user sets them by voice; Majordomo notifies them when due, including by push notification when the app is closed. | M |
| FR-27 | Calendar: read the user's schedule, and create or move events after confirmation (Google Calendar and Microsoft Outlook). | S |
| FR-28 | Email: read and summarize messages and draft replies; sending always needs confirmation (Gmail and Outlook). | S |
| FR-29 | Later tools, added as MCP servers: smart home, music, files, news, messaging, maps. | C |
| FR-26 | Smart-home control (e.g. Home Assistant). | C |

**Decided (2026-10-28):** the v1 extra tools are memory, reminders, calendar and email. Smart home, music, files, news, messaging and maps come later.

### 4.4 Memory and context
| ID | Requirement | Pri |
|---|---|---|
| FR-30 | Agent remembers context within a session. | M |
| FR-31 | Agent remembers user preferences and facts across sessions (per user). | M |
| FR-32 | User can view and delete what the agent remembers. | M |
| FR-33 | Conversation history is viewable in the client. | C |

### 4.5 Clients
| ID | Requirement | Pri |
|---|---|---|
| FR-40 | Web client (browser) with mic, camera, transcript, text input, and an animated "Majordomo" visualizer. | M |
| FR-41 | Mobile app for iOS and Android (Flutter). Built only if the installable web app (FR-44) falls short, e.g. for background listening or a wake word. | C |
| FR-42 | Desktop app or always-on desktop widget. | C |
| FR-43 | Clients show connection state, listening/speaking state, and errors in plain language. | M |
| FR-44 | The web client is installable on iPhone and Android home screens (PWA), with mic and camera working in mobile Safari and Chrome. | S |

### 4.6 Accounts and access
| ID | Requirement | Pri |
|---|---|---|
| FR-50 | On a hosted instance, users sign in before connecting, with Google or Microsoft (the same accounts used for calendar and email), or with an emailed sign-in link as a backup. Personal mode has no sign-in. | M |
| FR-51 | Each user's conversations, memory and tool credentials are isolated from other users. | M |
| FR-52 | Owner can invite/remove users and set per-user tool permissions. | S |
| FR-53 | Per-user usage limits to control cost. | S |
| FR-54 | Self-hosters can bring their own API keys via configuration. | M |
| FR-55 | Sign-up on a hosted instance is invite-only: only people the owner invites can create an account. | M |

## 5. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Latency:** time from end of user speech to start of agent audio under ~1 s typical (excluding tool calls). Tool calls give spoken feedback ("Let me check...") if they take over ~2 s. |
| NFR-2 | **Availability:** personal use, best effort; agent worker auto-restarts on crash; sessions resume after network drops (FR-9). |
| NFR-3 | **Cost:** free tiers are fine for Stan's own development and testing. A paid model key (or each user's own key) is used once other people use the assistant. Usage is logged per user so cost is visible, and a hard monthly spending cap stops paid usage when reached. |
| NFR-4 | **Privacy:** audio and video are not stored by default. Transcripts/memory stored only if enabled, and deletable. Other users' conversations never go through a free-tier model key, because free-tier content may be used to improve the provider's products. |
| NFR-5 | **Security:** API keys kept server-side, never in clients. Short-lived LiveKit tokens issued per session by the backend. All traffic over TLS. |
| NFR-6 | **Safety:** agent refuses or asks before risky actions; browser control is off for invited users. |
| NFR-7 | **Portability:** runs locally (macOS) for development and can deploy to a cloud host / container. |
| NFR-8 | **Maintainability:** config (persona, voice, model mode, tools, keys) in one config file / env vars; code documented with a setup guide a non-developer can follow. |
| NFR-9 | **Observability:** logs of sessions, tool calls and errors. |
| NFR-10 | **Accessibility:** text mode and transcript for users who can't use voice; readable UI on phone. |
| NFR-11 | **Deployment modes:** the same code runs as a hosted multi-user service or as a personal single-user install, chosen by config. A self-install works with only the user's own API keys and a LiveKit Cloud free account (or local LiveKit server). |
| NFR-12 | **Open source:** code published on GitHub under the Apache 2.0 license, with a setup guide and a one-command install. |
| NFR-13 | **Connected accounts:** calendar and email connect through each user's own sign-in (OAuth). Tokens are stored encrypted per user, and users can disconnect at any time. |
| NFR-14 | **Background jobs:** the backend runs scheduled jobs (reminders) and sends push notifications even when no conversation is open. |
| NFR-15 | **Containers:** agent, backend and web app ship as Docker images; one Docker Compose file starts a personal install. |
| NFR-16 | **No lock-in to LiveKit Cloud:** the system runs against LiveKit Cloud or a self-hosted LiveKit server by changing only the URL, API key and secret. Cloud-only features are optional. |
| NFR-17 | **Multi-architecture images:** every Docker image is built for both arm64 (GX10, Apple Silicon) and amd64 (typical cloud servers). |
| NFR-18 | **Optional GPU:** local-model containers (Ollama, Whisper) use an NVIDIA GPU when present, such as the GX10's, and are left out entirely when using cloud models. |

**Decided (2026-10-28):** start at about $20 a month while it's mainly Stan, with a hard monthly spending cap and per-user limits, and raise the budget as people are invited. As a rough guide, $10 a month covers Stan plus a few testers, and $100 a month covers 10 to 20 regular users. Self-installed copies cost Stan nothing, because they use their owners' own keys.

## 5a. Security

Points SEC-1 to SEC-4 are needed in phase 1; SEC-5 to SEC-7 come with the features they protect.

| ID | Requirement | Phase |
|---|---|---|
| SEC-1 | **Secrets:** API keys and secrets live in a `.env` file that is never committed (listed in `.gitignore`; a `.env.example` with blank values is committed instead). Secret scanning and push protection are on for the public GitHub repo. | 1 |
| SEC-2 | **Tokens, not keys:** the browser and apps only ever receive short-lived LiveKit access tokens issued by the backend, never the LiveKit, Gemini or other API keys. | 1 |
| SEC-3 | **Spending caps:** hard budget caps and alerts are set in Google Cloud (Gemini) and LiveKit before anyone other than Stan uses the hosted instance. | 1 |
| SEC-4 | **HTTPS everywhere:** all web, API and LiveKit connections use TLS; no plain HTTP in hosted mode. | 1 |
| SEC-5 | **Tool guardrails:** Majordomo confirms before sending email, submitting forms, buying anything or deleting anything. Content from web pages and emails is treated as untrusted data, never as instructions (prompt-injection defense). | 2 to 4 |
| SEC-6 | **User separation:** each user's conversations, memory and connected accounts are isolated; OAuth tokens are stored encrypted and can be revoked by the user. | 2 to 4 |
| SEC-7 | **No recording by default:** audio and video are not recorded or stored unless a user turns it on, and the hosted instance's privacy notice says so. | 4 |

## 6. Integrations and dependencies

| Component | Choice | Notes |
|---|---|---|
| Real-time transport | LiveKit Cloud (free tier) now; self-hosted LiveKit server later | Switch by config; Cloud-only extras optional |
| Hosting | Docker containers (agent, backend, web app); Docker Compose for personal installs | Self-hosted LiveKit needs host networking and open ports |
| Deployment targets | Cloud server (hosted mode); ASUS Ascent GX10 (personal mode, development, local models) | GX10 needs no open ports with LiveKit Cloud; HTTPS via Cloudflare Tunnel |
| Agent framework | LiveKit Agents (Python) | Per tutorial; supports MCP tools and both model modes |
| LLM / voice (default) | Google Gemini Live API | Session resumption + context compression on; paid key before sharing |
| LLM / voice (backup) | Claude with separate STT + TTS (pipeline mode) | Selected by config; slower replies, stronger tool use |
| LLM / voice (local, later) | Ollama (Gemma 3 or Qwen) + Whisper + Kokoro/Piper | Optional; free and private; owner's Mac only |
| Web search | Gemini built-in Google Search | Tavily/Brave only in pipeline mode |
| Weather | Open-Meteo | Free, no key |
| Browser control | Playwright MCP server on the owner's Mac | Off for invited users |
| Mobile | Installable web app (PWA) | Flutter + LiveKit Flutter SDK only if needed |
| Auth | Ready-made auth service (e.g. Supabase Auth): Google, Microsoft, emailed sign-in link | Invite-only; hosted mode only |
| Storage (memory/history) | SQLite locally, Postgres when hosted | |

## 7. Phased plan

1. **Phase 1, Foundation:** LiveKit + Gemini Live voice agent with persona, running locally; basic web client; session resumption and context compression on. (FR-1–5, FR-9, FR-40, FR-43)
2. **Phase 2, Tools and backend:** built-in search, weather, camera vision, confirmation for side-effect actions; sign-in, token server, per-user storage, logging. (FR-10, 12, 20, 21, 23, 30, 50, 51, 54; NFR-5, NFR-9)
3. **Phase 3, Browser control and polish:** Playwright MCP browser tool on Stan's Mac with confirmations; custom Majordomo UI; voice selection; screen share; reminders and cross-session memory. (FR-6, 11, 22, 24, 25, 31, 32; NFR-14)
4. **Phase 4, Share it:** installable mobile web app, paid model key, usage limits, invites, calendar and email. (FR-27, 28, 44, 52, 53; NFR-13)
5. **Later:** Flutter app (only if needed), wake word, calendar/email/reminders, smart home, desktop app.

## 8. Acceptance criteria (v1)

- Stan can open the web client, say "Domo, what's the weather in <city> tomorrow?" and hear a correct spoken answer within a few seconds.
- Stan can interrupt a long answer and the agent stops within about 1 s (tighten once measured).
- With camera on, "What am I holding?" gets a correct description, and a 10-minute camera session does not drop.
- "Search for today's news about <topic>" returns current results with sources in the transcript.
- Browser tool can open a site and read back its headline; it asks before submitting any form.
- A second user can sign in on their phone and cannot see Stan's history or memory.
- A new user can follow the setup guide and get the agent running locally in under 30 minutes.

## 9. Risks and assumptions

- **Free-tier limits and terms** (Gemini, LiveKit) may change or throttle; keep the pipeline fallback working.
- **Gemini Live session limits** cut conversations short unless resumption and compression are on.
- **Browser control** is the highest-risk tool (security, reliability); keep it on the owner's Mac and confirmation-gated.
- **Mobile web limits:** a PWA can't listen in the background or use a system wake word; that is the trigger for building the Flutter app.
- **Privacy** obligations increase once other people's audio/video passes through the system.
- **Google app review:** on the hosted instance, reading Gmail needs Google's app verification and a yearly security assessment once more than 100 users connect. Until then, the app stays in Google's testing mode, which allows up to 100 users. Self-installed copies use their own Google project and avoid this.
- **Self-hosting LiveKit** needs a public server with open UDP and TCP media ports and TLS; harder to run than LiveKit Cloud, so it stays a later option.
- **iPhone notifications:** web push on iPhone works only after the web app is added to the home screen.
- Assumes the tutorial's code (`ruxakK/jarvis-voice...`) is a starting point, not a dependency to maintain.

## 10. Decisions

All questions settled (2026-10-28): browser control runs on Stan's Mac only; phones use an installable web app first; web search uses Gemini's built-in Google Search; Gemini Live is the main model with Claude as backup; Stan hosts a shared instance and others can also self-install; the code is published on GitHub under Apache 2.0; each user picks their form of address, and the default tone is dry and witty; v1 extra tools are memory, reminders, calendar and email; hosted users sign in with Google, Microsoft or an email link, by invite only; everything runs in Docker, with LiveKit Cloud now and self-hosted LiveKit as a later option; the hosted budget starts at about $20 a month with a hard cap; v1 uses tap-to-talk, and the wake word comes later.
