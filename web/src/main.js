// Majordomo web client: tap-to-talk voice, typed messages and a live transcript.
// It only ever receives a short-lived LiveKit token from the backend (SEC-2).
import { ConnectionState, Room, RoomEvent, Track } from 'livekit-client';

const $ = (id) => document.getElementById(id);
const ui = {
  status: $('status'),
  talk: $('talk'),
  talkLabel: $('talk-label'),
  hint: $('hint'),
  error: $('error'),
  log: $('log'),
  chat: $('chat'),
  chatInput: $('chat-input'),
  chatSend: $('chat-send'),
  hangup: $('hangup'),
  access: $('access'),
  accessCode: $('access-code'),
};

const ACCESS_KEY = 'majordomo.accessCode';
let room = null;
let connecting = false;
let micOn = false;
let agentState = 'idle';
let accessRequired = false;
const segments = new Map(); // transcript segment id -> <li>

// ---------- plain-language status and errors (FR-43) ----------

const STATE_TEXT = {
  idle: 'Not connected',
  connecting: 'Connecting…',
  initializing: 'Domo is getting ready…',
  listening: 'Listening',
  thinking: 'Thinking…',
  speaking: 'Speaking',
  reconnecting: 'Connection lost, reconnecting…',
};

function render() {
  const state = connecting ? 'connecting' : room ? (micOn && agentState === 'listening' ? 'listening' : agentState) : 'idle';
  ui.status.textContent = room && !micOn && agentState === 'listening' ? 'Connected, mic off' : STATE_TEXT[state] ?? state;
  ui.talk.dataset.state = state;
  ui.talk.dataset.mic = micOn ? 'on' : 'off';
  ui.talk.setAttribute('aria-pressed', String(micOn));
  ui.talkLabel.textContent = !room ? 'Tap to talk' : micOn ? 'Tap to stop' : 'Tap to talk';
  const connected = Boolean(room);
  ui.chatInput.disabled = !connected;
  ui.chatSend.disabled = !connected;
  ui.hangup.hidden = !connected;
  ui.hint.hidden = connected && micOn;
}

function showError(message) {
  ui.error.textContent = message;
  ui.error.hidden = !message;
}

function friendlyError(err) {
  const name = err?.name ?? '';
  if (name === 'NotAllowedError') return 'Microphone access was blocked. Allow the microphone for this site in your browser settings, then try again.';
  if (name === 'NotFoundError') return "No microphone was found. Plug one in, or type a message instead.";
  if (!navigator.onLine) return "You're offline. Check your internet connection.";
  if (/signal connection|websocket/i.test(err?.message ?? '')) {
    return "Couldn't reach the voice server (LiveKit). Check LIVEKIT_URL in .env and your internet connection.";
  }
  return err?.message || 'Something went wrong. Please try again.';
}

// ---------- backend ----------

async function checkBackend() {
  try {
    const res = await fetch('/api/health');
    const info = await res.json();
    accessRequired = Boolean(info.access_code_required);
    if (!info.livekit_configured) {
      showError("Majordomo isn't set up yet: LiveKit keys are missing on the server. See the README, 'Getting your keys'.");
    }
    if (accessRequired && !getAccessCode()) ui.access.hidden = false;
  } catch {
    showError("Can't reach the Majordomo server. Is it running?");
  }
}

function getAccessCode() {
  try { return sessionStorage.getItem(ACCESS_KEY) || ''; } catch { return ''; }
}

async function fetchToken() {
  const headers = { 'Content-Type': 'application/json' };
  if (accessRequired) headers['X-Access-Code'] = getAccessCode();
  const res = await fetch('/api/token', { method: 'POST', headers });
  if (res.status === 401) {
    ui.access.hidden = false;
    throw new Error('Please enter the access code you were given.');
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `The server said no (${res.status}).`);
  return body;
}

// ---------- LiveKit room ----------

async function connect() {
  if (room || connecting) return;
  connecting = true;
  showError('');
  render();
  try {
    const { server_url, participant_token } = await fetchToken();
    const r = new Room({ adaptiveStream: true, dynacast: true });
    wireRoom(r);
    await r.connect(server_url, participant_token);
    await r.startAudio(); // we're inside a tap, so autoplay is allowed
    room = r;
    agentState = 'initializing';
    await setMic(true);
  } catch (err) {
    console.error(err);
    showError(friendlyError(err));
    await disconnect();
  } finally {
    connecting = false;
    render();
  }
}

async function disconnect() {
  const r = room;
  room = null;
  micOn = false;
  agentState = 'idle';
  if (r) await r.disconnect();
  render();
}

async function setMic(on) {
  if (!room) return;
  try {
    await room.localParticipant.setMicrophoneEnabled(on, { echoCancellation: true, noiseSuppression: true, autoGainControl: true });
    micOn = on;
  } catch (err) {
    micOn = false;
    showError(friendlyError(err));
  }
  render();
}

function wireRoom(r) {
  r.on(RoomEvent.TrackSubscribed, (track) => {
    if (track.kind === Track.Kind.Audio) {
      const el = track.attach();
      el.hidden = true;
      document.body.appendChild(el);
    }
  });
  r.on(RoomEvent.TrackUnsubscribed, (track) => track.detach().forEach((el) => el.remove()));

  r.on(RoomEvent.ParticipantAttributesChanged, (changed, participant) => {
    if (participant.isAgent && changed['lk.agent.state']) {
      agentState = changed['lk.agent.state'];
      render();
    }
  });

  r.on(RoomEvent.ConnectionStateChanged, (state) => {
    if (state === ConnectionState.Reconnecting) { agentState = 'reconnecting'; render(); }
    if (state === ConnectionState.Connected && agentState === 'reconnecting') { agentState = 'listening'; render(); }
  });

  r.on(RoomEvent.Disconnected, () => {
    if (room === r) {
      room = null;
      micOn = false;
      agentState = 'idle';
      showError('The session ended. Tap to talk to start a new one.');
      render();
    }
  });

  r.on(RoomEvent.ParticipantDisconnected, (p) => {
    if (p.isAgent && room === r) {
      showError('Domo left the conversation. Tap to talk to start again.');
      disconnect();
    }
  });

  // Live transcript of both sides (FR-4).
  r.registerTextStreamHandler('lk.transcription', async (reader, from) => {
    const attrs = reader.info.attributes ?? {};
    const id = attrs['lk.segment_id'] ?? reader.info.id;
    const trackId = attrs['lk.transcribed_track_id'];
    const isMe = from.identity === r.localParticipant.identity
      || (trackId && r.localParticipant.trackPublications.has(trackId));
    const li = segmentFor(id, isMe ? 'me' : 'domo');
    for await (const chunk of reader) {
      li.querySelector('.text').textContent += chunk;
      scrollLog();
    }
  });
}

// ---------- transcript ----------

function segmentFor(id, who) {
  let li = segments.get(id);
  if (!li) {
    li = document.createElement('li');
    li.className = `msg ${who}`;
    const label = document.createElement('span');
    label.className = 'who';
    label.textContent = who === 'me' ? 'You' : 'Domo';
    const text = document.createElement('span');
    text.className = 'text';
    li.append(label, text);
    ui.log.appendChild(li);
    segments.set(id, li);
  }
  return li;
}

function scrollLog() {
  ui.log.lastElementChild?.scrollIntoView({ block: 'end', behavior: 'smooth' });
}

// ---------- visualizer: the ring follows Domo's voice ----------

function animate() {
  let level = 0;
  if (room) {
    for (const p of room.remoteParticipants.values()) if (p.isAgent) level = Math.max(level, p.audioLevel);
    if (micOn) level = Math.max(level, room.localParticipant.audioLevel * 0.6);
  }
  ui.talk.style.setProperty('--level', level.toFixed(3));
  requestAnimationFrame(animate);
}

// ---------- events ----------

ui.talk.addEventListener('click', async () => {
  if (!room) return connect();
  await setMic(!micOn);
});

ui.hangup.addEventListener('click', () => disconnect());

ui.chat.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = ui.chatInput.value.trim();
  if (!text || !room) return;
  ui.chatInput.value = '';
  const li = segmentFor(`typed-${Date.now()}`, 'me');
  li.querySelector('.text').textContent = text;
  scrollLog();
  try {
    await room.localParticipant.sendText(text, { topic: 'lk.chat' });
  } catch (err) {
    showError(friendlyError(err));
  }
});

ui.access.addEventListener('submit', (e) => {
  e.preventDefault();
  try { sessionStorage.setItem(ACCESS_KEY, ui.accessCode.value.trim()); } catch { /* private mode */ }
  ui.access.hidden = true;
  showError('');
});

window.addEventListener('offline', () => showError("You're offline. Domo will reconnect when you're back."));
window.addEventListener('online', () => showError(''));

render();
checkBackend();
requestAnimationFrame(animate);
