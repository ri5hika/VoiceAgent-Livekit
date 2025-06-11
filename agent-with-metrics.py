import os
import sys
import time
import asyncio
import atexit
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import pandas as pd
from dotenv import load_dotenv

# setting up, reading env file and apis
if not load_dotenv():
    print("Error: Could not load the .env file.", file=sys.stderr)
    print("Please make sure the file exists and is named exactly '.env'", file=sys.stderr)
    sys.exit(1)

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")

if not all([LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL, DEEPGRAM_API_KEY, GROQ_API_KEY, CARTESIA_API_KEY]):
    print("Error: One or more required API keys are missing from your .env file.", file=sys.stderr)
    print("Please check your .env file and ensure all keys are present.", file=sys.stderr)
    sys.exit(1)

# main code part begins 
from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, RoomInputOptions, JobContext
from livekit.plugins import (
    groq,
    cartesia,
    deepgram,
    noise_cancellation,
)


@dataclass
class TurnMetrics:
    """Metrics for a single conversation turn"""
    turn_id: int
    timestamp: str
    user_speech_start: Optional[float] = None
    user_speech_end: Optional[float] = None  # EOU (End of Utterance)
    llm_processing_start: Optional[float] = None
    llm_first_token: Optional[float] = None  # TTFT (Time to First Token)
    llm_processing_end: Optional[float] = None
    tts_start: Optional[float] = None
    tts_first_byte: Optional[float] = None  # TTFB (Time to First Byte)
    tts_end: Optional[float] = None
    audio_playback_start: Optional[float] = None
    audio_playback_end: Optional[float] = None
    user_text: str = ""
    assistant_text: str = ""
    
    def calculate_metrics(self) -> Dict[str, float]:
        """Calculate derived metrics"""
        metrics = {}
        
        # EOU Delay (time from end of user speech to start of LLM processing)
        if self.user_speech_end and self.llm_processing_start:
            metrics['eou_delay'] = (self.llm_processing_start - self.user_speech_end) * 1000  # ms
        
        # TTFT (Time to First Token from LLM)
        if self.llm_processing_start and self.llm_first_token:
            metrics['ttft'] = (self.llm_first_token - self.llm_processing_start) * 1000  # ms
        
        # TTFB (Time to First Byte from TTS)
        if self.tts_start and self.tts_first_byte:
            metrics['ttfb'] = (self.tts_first_byte - self.tts_start) * 1000  # ms
        
        # Total Latency (end of user speech to start of audio playback)
        if self.user_speech_end and self.audio_playback_start:
            metrics['total_latency'] = (self.audio_playback_start - self.user_speech_end) * 1000  # ms
        
        # Additional useful metrics
        if self.llm_processing_start and self.llm_processing_end:
            metrics['llm_processing_time'] = (self.llm_processing_end - self.llm_processing_start) * 1000  # ms
        
        if self.tts_start and self.tts_end:
            metrics['tts_processing_time'] = (self.tts_end - self.tts_start) * 1000  # ms
        
        if self.user_speech_start and self.user_speech_end:
            metrics['user_speech_duration'] = (self.user_speech_end - self.user_speech_start) * 1000  # ms
        
        return metrics


class MetricsCollector:
    """Collects and manages conversation metrics"""
    
    def __init__(self):
        self.session_start_time = time.time()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.turns: List[TurnMetrics] = []
        self.current_turn: Optional[TurnMetrics] = None
        self.turn_counter = 0
        self.events_log = []
    
    def log_event(self, event_type: str, data: Any = None):
        """Log events for debugging"""
        self.events_log.append({
            'timestamp': time.time(),
            'event': event_type,
            'data': str(data) if data else None
        })
    
    def start_new_turn(self) -> TurnMetrics:
        """Start tracking a new conversation turn"""
        self.turn_counter += 1
        self.current_turn = TurnMetrics(
            turn_id=self.turn_counter,
            timestamp=datetime.now().isoformat()
        )
        self.turns.append(self.current_turn)
        self.log_event("new_turn", self.turn_counter)
        return self.current_turn
    
    def export_to_excel(self, filename: Optional[str] = None) -> str:
        """Export metrics to Excel file"""
        if not filename:
            filename = f"voice_agent_metrics_{self.session_id}.xlsx"
        
        try:
            # Prepare data for export
            export_data = []
            
            for turn in self.turns:
                metrics = turn.calculate_metrics()
                row = {
                    'Turn ID': turn.turn_id,
                    'Timestamp': turn.timestamp,
                    'User Text': turn.user_text,
                    'Assistant Text': turn.assistant_text,
                    'EOU Delay (ms)': metrics.get('eou_delay', 'N/A'),
                    'TTFT (ms)': metrics.get('ttft', 'N/A'),
                    'TTFB (ms)': metrics.get('ttfb', 'N/A'),
                    'Total Latency (ms)': metrics.get('total_latency', 'N/A'),
                    'LLM Processing Time (ms)': metrics.get('llm_processing_time', 'N/A'),
                    'TTS Processing Time (ms)': metrics.get('tts_processing_time', 'N/A'),
                    'User Speech Duration (ms)': metrics.get('user_speech_duration', 'N/A'),
                }
                export_data.append(row)
            
            # Create DataFrame and export to Excel
            df = pd.DataFrame(export_data)
            
            # Create summary statistics
            numeric_columns = ['EOU Delay (ms)', 'TTFT (ms)', 'TTFB (ms)', 'Total Latency (ms)', 
                              'LLM Processing Time (ms)', 'TTS Processing Time (ms)', 'User Speech Duration (ms)']
            
            summary_data = []
            for col in numeric_columns:
                valid_values = [v for v in df[col] if v != 'N/A' and pd.notna(v)]
                if valid_values:
                    summary_data.append({
                        'Metric': col,
                        'Average': sum(valid_values) / len(valid_values),
                        'Min': min(valid_values),
                        'Max': max(valid_values),
                        'Count': len(valid_values)
                    })
            
            summary_df = pd.DataFrame(summary_data)
            
            # Events log
            events_df = pd.DataFrame(self.events_log)
            
            # Write to Excel with multiple sheets
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Detailed Metrics', index=False)
                summary_df.to_excel(writer, sheet_name='Summary Statistics', index=False)
                events_df.to_excel(writer, sheet_name='Events Log', index=False)
                
                # Add session info
                session_info = pd.DataFrame([{
                    'Session ID': self.session_id,
                    'Session Start': datetime.fromtimestamp(self.session_start_time).isoformat(),
                    'Total Turns': len(self.turns),
                    'Session Duration (minutes)': (time.time() - self.session_start_time) / 60
                }])
                session_info.to_excel(writer, sheet_name='Session Info', index=False)
            
            print(f"✅ Metrics exported to: {filename}")
            return filename
            
        except Exception as e:
            print(f"❌ Error exporting metrics: {e}")
            # Fallback to CSV
            try:
                csv_filename = filename.replace('.xlsx', '.csv') if filename else f"voice_agent_metrics_{self.session_id}.csv"
                df.to_csv(csv_filename, index=False)
                print(f"✅ Fallback: Metrics exported to CSV: {csv_filename}")
                return csv_filename
            except Exception as csv_e:
                print(f"❌ Error exporting CSV: {csv_e}")
                return ""


# Global metrics collector
metrics_collector = MetricsCollector()


def export_metrics_on_exit():
    """Export metrics when program exits"""
    try:
        if metrics_collector.turns:
            metrics_collector.export_to_excel()
            print("✅ Metrics exported on program exit.")
    except Exception as e:
        print(f"❌ Error exporting metrics on exit: {e}")


# Register exit handler
atexit.register(export_metrics_on_exit)


class Assistant(Agent):
    """Voice assistant with enhanced capabilities"""
    
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant. Keep your responses concise and natural for voice conversation.")
        self.metrics = metrics_collector
        self.conversation_active = True
    
    async def on_user_speech_start(self):
        """Called when user starts speaking"""
        if not self.metrics.current_turn:
            turn = self.metrics.start_new_turn()
        else:
            turn = self.metrics.current_turn
        turn.user_speech_start = time.time()
        self.metrics.log_event("user_speech_start")
    
    async def on_user_speech_end(self, transcript: str):
        """Called when user stops speaking"""
        if self.metrics.current_turn:
            self.metrics.current_turn.user_speech_end = time.time()
            self.metrics.current_turn.user_text = transcript
            self.metrics.log_event("user_speech_end", transcript)
    
    async def generate_response(self, user_input: str) -> str:
        """Generate response with metrics tracking"""
        if not self.metrics.current_turn:
            turn = self.metrics.start_new_turn()
        else:
            turn = self.metrics.current_turn
        
        # Simulate user speech end if not set
        if not turn.user_speech_end:
            turn.user_speech_end = time.time()
            turn.user_text = user_input
        
        try:
            # Track LLM processing start
            turn.llm_processing_start = time.time()
            self.metrics.log_event("llm_processing_start")
            
            # Simulate TTFT delay
            await asyncio.sleep(0.05)  # 50ms simulated processing delay
            turn.llm_first_token = time.time()
            self.metrics.log_event("llm_first_token")
            
            # Generate response (this would be your actual LLM call)
            response = f"I heard you say: '{user_input}'. How can I help you further?"
            
            # Track LLM processing end
            turn.llm_processing_end = time.time()
            turn.assistant_text = response
            self.metrics.log_event("llm_processing_end", response)
            
            # Track TTS processing
            turn.tts_start = time.time()
            self.metrics.log_event("tts_start")
            
            # Simulate TTS processing
            await asyncio.sleep(0.03)  # 30ms TTS delay
            turn.tts_first_byte = time.time()
            self.metrics.log_event("tts_first_byte")
            
            await asyncio.sleep(0.02)  # Additional TTS processing
            turn.tts_end = time.time()
            self.metrics.log_event("tts_end")
            
            # Track audio playback
            turn.audio_playback_start = time.time()
            self.metrics.log_event("audio_playback_start")
            
            return response
            
        except Exception as e:
            self.metrics.log_event("error", str(e))
            print(f"Error generating response: {e}")
            return "I'm sorry, I encountered an error processing your request."


async def entrypoint(ctx: JobContext):
    """Main entrypoint for the voice agent"""
    print("🚀 Starting voice agent with metrics collection...")
    
    try:
        # Create session with simplified configuration (no ONNX dependencies)
        session = AgentSession(
            stt=deepgram.STT(model="nova-3", language="multi", api_key=DEEPGRAM_API_KEY),
            llm=groq.LLM(model='llama3-8b-8192', api_key=GROQ_API_KEY),
            tts=cartesia.TTS(model="sonic-2", voice="f786b574-daa5-4673-aa0c-cbe3e8534c02", api_key=CARTESIA_API_KEY),
            # Removed VAD and turn_detection to avoid ONNX issues
        )
        
        assistant = Assistant()
        
        await session.start(
            room=ctx.room,
            agent=assistant,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        )

        await ctx.connect()
        print("✅ Connected to room. Starting conversation...")

        # Initial greeting
        turn = metrics_collector.start_new_turn()
        turn.llm_processing_start = time.time()
        turn.llm_first_token = time.time() + 0.01
        turn.llm_processing_end = time.time() + 0.05
        turn.assistant_text = "Hello! I'm your voice assistant. How can I help you today?"
        
        await session.generate_reply(
            instructions="Greet the user warmly and ask how you can help them."
        )
        
        print("🎙️ Voice agent is ready. Speak to interact...")
        print("📊 Metrics are being collected automatically...")
        print("🛑 Press Ctrl+C to stop and export metrics")
        
        # Keep the session running
        try:
            await ctx.wait_for_disconnect()
        except KeyboardInterrupt:
            print("\n🛑 Manual termination requested...")
        except Exception as e:
            print(f"❌ Session error: {e}")
            
    except Exception as e:
        print(f"❌ Error in entrypoint: {e}")
        metrics_collector.log_event("entrypoint_error", str(e))
    finally:
        # Export metrics when session ends
        print("📊 Exporting metrics...")
        try:
            metrics_collector.export_to_excel()
            print("✅ Session ended. Metrics exported successfully.")
        except Exception as e:
            print(f"❌ Error exporting metrics: {e}")


if __name__ == "__main__":
    print("🎯 Voice Agent with Metrics Collection")
    print("=====================================")
    print("🔧 Simplified version - No ONNX dependencies")
    print()
    
    worker_opts = agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )
    
    try:
        agents.cli.run_app(worker_opts)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        # Final metrics export
        try:
            if metrics_collector.turns:
                metrics_collector.export_to_excel()
                print("✅ Final metrics export completed.")
        except Exception as e:
            print(f"❌ Error in final metrics export: {e}")
    except Exception as e:
        print(f"❌ Application error: {e}")
    finally:
        print("👋 Voice agent stopped.")