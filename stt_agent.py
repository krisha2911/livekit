import os
import asyncio
import logging
from datetime import timedelta

from dotenv import load_dotenv
from livekit import rtc, token
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    stt,
    transcription,
)
from livekit.plugins import assemblyai # type: ignore

# Load .env variables
load_dotenv()

# Set up logging
logger = logging.getLogger("transcriber")

# Load environment values
LIVEKIT_URL = os.getenv("wss://voiceassistant29-evg225gc.livekit.cloud")
LIVEKIT_API_KEY = os.getenv("APIxN3fREFnHpy8")
LIVEKIT_API_SECRET = os.getenv("oFafjfUHpcyFMAuPMmeAe4Q7mzlbyq5nUhWrtuGedOZE")
LIVEKIT_ROOM = os.getenv("playground-x275-K2Fv")


async def entrypoint(ctx: JobContext):
    logger.info(f"Starting transcriber (speech to text), room: {LIVEKIT_ROOM}")
    stt_impl = assemblyai.STT()

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            asyncio.create_task(transcribe_track(participant, track))

    async def transcribe_track(participant: rtc.RemoteParticipant, track: rtc.Track):
        audio_stream = rtc.AudioStream(track)
        stt_forwarder = transcription.STTSegmentsForwarder(
            room=ctx.room, participant=participant, track=track
        )
        stt_stream = stt.SpeechStream(stt_impl)

        await asyncio.gather(
            _handle_audio_input(audio_stream, stt_stream),
            _handle_transcription_output(stt_stream, stt_forwarder),
        )

    async def _handle_audio_input(
        audio_stream: rtc.AudioStream, stt_stream: stt.SpeechStream
    ):
        async for ev in audio_stream:
            stt_stream.push_frame(ev.frame)

    async def _handle_transcription_output(
        stt_stream: stt.SpeechStream,
        stt_forwarder: transcription.STTSegmentsForwarder,
    ):
        async for ev in stt_stream:
            if ev.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                print(" ->", ev.alternatives[0].text)
                stt_forwarder.update(ev)

    # Generate token and connect
    access_token = token.AccessToken(
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        identity="transcriber-bot",
        ttl=timedelta(hours=1),
    )
    access_token.add_grant(token.VideoGrant(room=LIVEKIT_ROOM))
    token_str = access_token.to_jwt()

    await ctx.connect_to_room(
        url=LIVEKIT_URL,
        token=token_str,
        auto_subscribe=AutoSubscribe.AUDIO_ONLY,
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


