"""Majordomo voice agent: a LiveKit Agents worker that talks through Gemini Live.

Run locally:   python -m majordomo_agent.main dev
In Docker:     python -m majordomo_agent.main start
"""

from __future__ import annotations

import asyncio
import logging
import sys

from dotenv import load_dotenv
from google.genai import types
from livekit import rtc
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, room_io
from livekit.plugins import google

from .config import AgentSettings, missing_keys
from .persona import build_instructions, greeting_instructions

load_dotenv()
log = logging.getLogger("majordomo.agent")

settings = AgentSettings.from_env()
server = AgentServer()


def build_model(s: AgentSettings) -> google.realtime.RealtimeModel:
    """Gemini Live with the two settings that keep long sessions alive (FR-9).

    - Session resumption: if the Gemini connection drops or hits its time limit,
      the plugin reconnects with the last resumption handle and the conversation
      carries on where it left off.
    - Context window compression: once the context gets long, older turns are
      trimmed with a sliding window instead of the session being cut off
      (about 15 minutes audio-only, about 2 minutes with video, without it).
    """
    return google.realtime.RealtimeModel(
        model=s.gemini_model,
        voice=s.gemini_voice,
        temperature=0.8,
        session_resumption=types.SessionResumptionConfig(),
        context_window_compression=types.ContextWindowCompressionConfig(
            trigger_tokens=25_600,
            sliding_window=types.SlidingWindow(target_tokens=12_800),
        ),
        # Transcripts of both sides go to the web client (FR-4).
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # Gemini decides when you've finished speaking. The defaults can wait
        # forever if there's steady background noise, so end turns more readily.
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                silence_duration_ms=s.silence_ms,
            )
        ),
    )


class Majordomo(Agent):
    def __init__(self, s: AgentSettings) -> None:
        super().__init__(instructions=build_instructions(s.user_address, s.persona_extra))


async def _end_after(session: AgentSession, minutes: int) -> None:
    """Cost guard: politely end sessions that run past the configured limit."""
    await asyncio.sleep(minutes * 60)
    log.info("session limit of %s minutes reached; ending", minutes)
    try:
        handle = session.generate_reply(
            instructions="Tell the user, in one short sentence, that the session time limit "
            "has been reached and they can start a new one by tapping Connect."
        )
        await asyncio.wait_for(handle.wait_for_playout(), timeout=15)
    except Exception:  # noqa: BLE001 - ending anyway
        log.exception("could not say goodbye")
    session.shutdown()


@server.rtc_session(agent_name=settings.agent_name)
async def entrypoint(ctx: JobContext) -> None:
    log.info("joining room %s", ctx.room.name)
    session = AgentSession(llm=build_model(settings))

    await session.start(
        agent=Majordomo(settings),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=True,
            text_input=True,  # typed messages from the client (FR-3)
            video_input=False,  # camera arrives in phase 2 and stays off by default (FR-12)
            audio_output=True,
            text_output=True,
            close_on_disconnect=True,
            delete_room_on_close=True,
        ),
    )

    # Diagnostics: these lines in `docker compose logs agent` show whether
    # your voice is reaching Domo and what Gemini heard.
    @ctx.room.on("track_subscribed")
    def _on_track(track: rtc.Track, _pub: rtc.RemoteTrackPublication, p: rtc.RemoteParticipant) -> None:
        log.info("receiving %s from %s", rtc.TrackKind.Name(track.kind), p.identity)

    @session.on("user_input_transcribed")
    def _on_heard(ev) -> None:
        if ev.is_final:
            log.info("heard: %s", ev.transcript)

    @session.on("user_state_changed")
    def _on_user_state(ev) -> None:
        log.info("user is %s", ev.new_state)

    @ctx.room.local_participant.register_rpc_method("end_turn")
    async def end_turn(_data: rtc.RpcInvocationData) -> str:
        """The user tapped to stop talking. If Domo hasn't started answering yet,
        tell Gemini the turn is over instead of waiting for it to notice silence
        (a muted mic sends no audio at all, so it would never notice)."""
        if session.agent_state == "listening":
            log.info("user ended turn; asking for a reply")
            session.generate_reply()
            return "replying"
        return "busy"

    limiter = asyncio.create_task(_end_after(session, settings.max_session_minutes))

    async def stop_limiter() -> None:
        limiter.cancel()

    ctx.add_shutdown_callback(stop_limiter)

    await session.generate_reply(instructions=greeting_instructions(settings.user_address))


def main() -> None:
    missing = missing_keys()
    if missing and (len(sys.argv) < 2 or sys.argv[1] in ("start", "dev", "console", "connect")):
        print(
            "Majordomo can't start yet. Missing settings in .env: "
            + ", ".join(missing)
            + "\nSee README.md, 'Getting your keys'.",
            file=sys.stderr,
        )
        sys.exit(2)
    cli.run_app(server)


if __name__ == "__main__":
    main()
