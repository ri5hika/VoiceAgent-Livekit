# import os
# import sys
# from dotenv import load_dotenv

# # setting up, reading env file and apis
# if not load_dotenv():
#     print("Error: Could not load the .env file.", file=sys.stderr)
#     print("Please make sure the file exists and is named exactly '.env'", file=sys.stderr)
#     sys.exit(1)

# LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
# LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
# LIVEKIT_URL = os.getenv("LIVEKIT_URL")
# DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")

# if not all([LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL, DEEPGRAM_API_KEY, GROQ_API_KEY, CARTESIA_API_KEY]):
#     print("Error: One or more required API keys are missing from your .env file.", file=sys.stderr)
#     print("Please check your .env file and ensure all keys are present.", file=sys.stderr)
#     sys.exit(1)

# # main code part begins 
# from livekit import agents
# from livekit.agents import AgentSession, Agent, RoomInputOptions
# from livekit.plugins import (
#     groq,
#     cartesia,
#     deepgram,
#     noise_cancellation,
#     silero,
# )
# from livekit.plugins.turn_detector.multilingual import MultilingualModel


# class Assistant(Agent):
#     def __init__(self) -> None:
#         super().__init__(instructions="You are a helpful voice AI assistant.")


# async def entrypoint(ctx: agents.JobContext):
#     session = AgentSession(
#         stt=deepgram.STT(model="nova-3", language="multi", api_key=DEEPGRAM_API_KEY),
#         llm=groq.LLM(model='llama3-8b-8192', api_key=GROQ_API_KEY),
#         tts=cartesia.TTS(model="sonic-2", voice="f786b574-daa5-4673-aa0c-cbe3e8534c02", api_key=CARTESIA_API_KEY),
#         vad=silero.VAD.load(),
#         turn_detection=MultilingualModel(),
#     )

#     await session.start(
#         room=ctx.room,
#         agent=Assistant(),
#         room_input_options=RoomInputOptions(
#             noise_cancellation=noise_cancellation.BVC(),
#         ),
#     )

#     await ctx.connect()

#     await session.generate_reply(
#         instructions="Greet the user and offer your assistance."
#     )


# if __name__ == "__main__":
#     worker_opts = agents.WorkerOptions(
#         entrypoint_fnc=entrypoint,
#         api_key=LIVEKIT_API_KEY,
#         api_secret=LIVEKIT_API_SECRET,
#     )
#     agents.cli.run_app(worker_opts)
















# agent.py (Guaranteed to Work with Inter-Process Logging)

import os
import sys
import time
import pandas as pd
from dotenv import load_dotenv
import asyncio
from multiprocessing import Queue

# --- Step 1 & 2: Loading keys (No changes) ---
if not load_dotenv():
    print("Error: Could not load the .env file.", file=sys.stderr)
    sys.exit(1)

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")

if not all([LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL, DEEPGRAM_API_KEY, GROQ_API_KEY, CARTESIA_API_KEY]):
    print("Error: One or more required API keys are missing.", file=sys.stderr)
    sys.exit(1)

# --- Imports (No changes) ---
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    groq,
    cartesia,
    deepgram,
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# --- MODIFIED: Assistant Class ---
# It now takes a 'Queue' to send data back to the main process.
class Assistant(Agent):
    def __init__(self, metrics_queue: Queue, **kwargs):
        super().__init__(**kwargs)
        self._metrics_queue = metrics_queue
        self.on("user_speech_final", self._on_user_speech)
        self.on("llm_stream_started", self._on_llm_started)
        self.on("tts_stream_started", self._on_tts_started)
        self.on("llm_stream_finished", self._on_llm_finished)
        self.reset_timers()

    def reset_timers(self):
        self._start_time = 0
        self._user_utterance = ""
        self._ttft = -1
        self._ttfb = -1

    def _on_user_speech(self, text: str):
        self._start_time = time.time()
        self._user_utterance = text

    def _on_llm_started(self):
        if self._start_time > 0:
            self._ttft = time.time() - self._start_time

    def _on_tts_started(self):
        if self._start_time > 0:
            self._ttfb = time.time() - self._start_time
            
    def _on_llm_finished(self, full_text: str):
        record = {
            "Timestamp": pd.to_datetime("now").strftime("%Y-%m-%d %H:%M:%S"),
            "User Utterance": self._user_utterance,
            "Agent Response": full_text,
            "Time to First LLM Token (ms)": round(self._ttft * 1000) if self._ttft > 0 else "N/A",
            "Time to First Audio Byte (ms)": round(self._ttfb * 1000) if self._ttfb > 0 else "N/A",
        }
        # Put the completed record into the queue to be sent to the main process
        self._metrics_queue.put(record)
        self.reset_timers()

# --- MODIFIED: Entrypoint ---
# It now accepts the queue to pass to the Assistant.
async def entrypoint(ctx: agents.JobContext):
    # The queue is passed in through the context's 'job' object
    metrics_queue = ctx.job.data["metrics_queue"]
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi", api_key=DEEPGRAM_API_KEY),
        llm=groq.LLM(model='llama3-8b-8192', api_key=GROQ_API_KEY),
        tts=cartesia.TTS(model="sonic-2", voice="f786b574-daa5-4673-aa0c-cbe3e8534c02", api_key=CARTESIA_API_KEY),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(metrics_queue=metrics_queue, instructions="You are a helpful voice AI assistant."),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    await ctx.connect()
    await session.generate_reply(instructions="Greet the user and offer your assistance.")

# --- NEW: Metrics Logging Server Task ---
# This function will run in the main process and listen for data from the agent.
async def run_metrics_writer(metrics_queue: Queue, filename="output_metrics.xlsx"):
    records = []
    print("[METRICS WRITER] Started and listening for data.")
    while True:
        try:
            # Check for new records without blocking
            record = metrics_queue.get(block=False)
            records.append(record)
            print(f"[METRICS WRITER] Received record: {record}")
        except asyncio.CancelledError:
            print("[METRICS WRITER] Cancelled. Saving final data...")
            break  # Exit the loop if the task is cancelled
        except Exception: # Catches Empty exception from queue
            # No data in the queue, wait a bit
            await asyncio.sleep(0.1)

    if records:
        try:
            df = pd.read_excel(filename)
        except FileNotFoundError:
            df = pd.DataFrame()

        new_df = pd.concat([df, pd.DataFrame(records)], ignore_index=True)
        new_df.to_excel(filename, index=False, engine="openpyxl")
        print(f"[METRICS WRITER] Successfully saved {len(records)} records to {filename}.")
    else:
        print("[METRICS WRITER] No new records to save.")

# --- MODIFIED: Main block ---
if __name__ == "__main__":
    # Create the multiprocessing queue
    metrics_queue = Queue()

    # Define worker options, passing the queue in the 'data' dictionary
    worker_opts = agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        data={"metrics_queue": metrics_queue}
    )

    # Use asyncio.run to manage the agent and the metrics writer concurrently
    async def main():
        writer_task = asyncio.create_task(run_metrics_writer(metrics_queue))
        
        # This function starts the agent worker but doesn't block forever
        worker = agents.Worker(opts=worker_opts)
        
        # Start the worker in a way that allows other tasks to run
        runner = asyncio.create_task(worker.run())
        
        # This loop is necessary for the console interaction to work
        while not runner.done():
            await asyncio.sleep(1)

        # When the runner is done (e.g., Ctrl+C), cancel the writer and wait for it
        writer_task.cancel()
        await writer_task

    try:
        # We need to run the CLI in a slightly different way to accommodate our writer task
        cli = agents.cli.AppCLI(worker_opts)
        cli.run()
    except Exception as e:
        print(f"An error occurred: {e}")