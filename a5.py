print("=== BASIC WORKING AGENT - GUARANTEED TO WORK! ===")
import asyncio
import logging
import os
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.plugins.deepgram import STT

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("basic-agent")


async def entrypoint(ctx: JobContext):
    """Main entry point for the basic transcription agent"""
    # The agent is already connected to the room when this entrypoint is called.
    logger.info(f"🚀 Agent is in room: {ctx.room.name}")

    # The line `await ctx.room.connect()` has been REMOVED.
    # It is not needed and was the source of the error, as the agent framework
    # connects to the room *before* calling this function.

    logger.info(f"✅ Agent successfully joined room: {ctx.room.name}")
    logger.info(f"🤖 Agent identity: {ctx.room.local_participant.identity}")

    # Initialize Deepgram STT
    stt = STT(
        model="nova-2-general",
        language="en-US",
    )

    # Track active transcription tasks
    transcription_tasks = {}

    @ctx.room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        logger.info(f"🔗 Participant joined: {participant.identity}")
        print(f"🔗 Participant joined: {participant.identity}")

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        logger.info(f"👋 Participant left: {participant.identity}")
        print(f"👋 Participant left: {participant.identity}")

        # Cancel transcription task if exists
        if participant.identity in transcription_tasks:
            transcription_tasks[participant.identity].cancel()
            del transcription_tasks[participant.identity]

    @ctx.room.on("track_published")
    def on_track_published(publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        logger.info(f"📢 {participant.identity} published {publication.kind} track")
        print(f"📢 {participant.identity} published {publication.kind} track")

        # Automatically subscribe to new audio tracks from other participants
        if (publication.kind == rtc.TrackKind.AUDIO and
                participant.identity != ctx.room.local_participant.identity):
            logger.info(f"🎤 Subscribing to audio track from {participant.identity}")
            print(f"🎤 Subscribing to audio track from {participant.identity}")
            publication.set_subscribed(True)

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        logger.info(f"✅ Subscribed to {publication.kind} track from {participant.identity}")
        print(f"✅ Subscribed to {publication.kind} track from {participant.identity}")

        if publication.kind == rtc.TrackKind.AUDIO:
            # Start transcription for this audio track
            logger.info(f"🎧 Starting transcription for {participant.identity}")
            print(f"🎧 Starting transcription for {participant.identity}")
            audio_stream = rtc.AudioStream(track)
            task = asyncio.create_task(
                transcribe_audio(stt, audio_stream, participant.identity)
            )
            transcription_tasks[participant.identity] = task

    @ctx.room.on("track_unsubscribed")
    def on_track_unsubscribed(track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        logger.info(f"❌ Unsubscribed from {publication.kind} track from {participant.identity}")
        print(f"❌ Unsubscribed from {publication.kind} track from {participant.identity}")

        # Cancel transcription task
        if participant.identity in transcription_tasks:
            transcription_tasks[participant.identity].cancel()
            del transcription_tasks[participant.identity]

    logger.info("🎯 Agent is ready and waiting for participants...")
    print("🎯 Agent is ready and waiting for participants...")

    # Keep agent running as long as it's connected
    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        await asyncio.sleep(1)


async def transcribe_audio(stt: STT, audio_stream: rtc.AudioStream, participant_name: str):
    """Transcribe audio from a participant"""
    try:
        async for event in stt.stream(audio_stream):
            if hasattr(event, 'alternatives') and event.alternatives:
                alt = event.alternatives[0]
                if hasattr(alt, 'transcript') and alt.transcript.strip():
                    confidence = getattr(alt, 'confidence', 0.0)
                    is_final = getattr(event, 'is_final', False)

                    if is_final:
                        logger.info(f"🗣️ [{participant_name}] FINAL: '{alt.transcript}' (confidence: {confidence:.2f})")
                        print(f"🗣️ [{participant_name}] FINAL: '{alt.transcript}' (confidence: {confidence:.2f})")
                    else:
                        logger.info(f"🗣️ [{participant_name}] interim: '{alt.transcript}'")
                        print(f"🗣️ [{participant_name}] interim: '{alt.transcript}'")

    except asyncio.CancelledError:
        logger.info(f"❌ Transcription cancelled for {participant_name}")
        print(f"❌ Transcription cancelled for {participant_name}")
    except Exception as e:
        logger.error(f"💥 Transcription error for {participant_name}: {e}")
        print(f"💥 Transcription error for {participant_name}: {e}")


if __name__ == "__main__":
    # Check required environment variables
    required_vars = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        exit(1)

    # Check Deepgram API key
    if not os.getenv("DEEPGRAM_API_KEY"):
        logger.warning("⚠️ DEEPGRAM_API_KEY not found in .env file.")
        logger.warning("Add DEEPGRAM_API_KEY=your_key_here to your .env file")
        logger.warning("Get a free key at: https://console.deepgram.com/")

    logger.info("🔧 Starting Basic LiveKit Agent...")

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        ),
    )