# AI Voice Agent using LiveKit, Deepgram, GROQ, and Cartesia
This project implements a real-time voice-based AI assistant using LiveKit's Agent framework. It integrates automatic speech recognition (ASR), natural language processing (LLM), speech-to-text (STT) and text-to-speech (TTS) using APIs from Deepgram, GROQ, and Cartesia, along with multilingual voice activity detection and noise cancellation.

# Video Demo
Check out the various video demos for this AI voice agent here: 
https://drive.google.com/drive/folders/1IUN5ksWcgtq1qUhVH2MT9sqCmm_vmb1r?usp=drive_link

# Features
1. Speech-to-Text: Real-time transcription using Deepgram (nova-3 model)
2. Natural Language Understanding: LLM-based reasoning and response generation using GROQ (llama3-8b-8192)
3. Text-to-Speech: Lifelike audio responses with Cartesia (sonic-2 model and voice ID)
4. Noise Cancellation: Real-time BVC noise suppression
5. Multilingual Turn Detection: Accurate detection of speaker turns
6. LiveKit Agent Framework: Audio room management and agent lifecycle

# Setup
1. Clone the Repository:
   git clone <your-repo-url>
   cd <your-repo-directory>

2. Create a .env File (get the API keys for the following from their officail websites):
   LIVEKIT_API_KEY=your_livekit_api_key
   LIVEKIT_API_SECRET=your_livekit_api_secret
   LIVEKIT_URL=your_livekit_url
   DEEPGRAM_API_KEY=your_deepgram_api_key
   GROQ_API_KEY=your_groq_api_key
   CARTESIA_API_KEY=your_cartesia_api_key

4. Install Dependencies:
   pip install -r requirements.txt

5. Run in your Console:
   python your_script_name.py console

# Note
This repository has two seperate scripts.
1. agent.py - It simply runs the AI voice agent.
2. agent-with-metrics.py - It runs the AI voice agent as well as generates real time metrics of the chat and saves it in an excel file.

# Metrics
During each call session, the following key latency metrics are logged and saved for performance analysis:
1. EOU Delay (End of Utterance Delay):
   Time taken to detect the end of a speaker's utterance and begin processing it. A lower EOU delay ensures faster responsiveness of the voice agent.
2. TTFT (Time to First Token):
   Duration between the end of speech and the generation of the first token by the transcription or language model. This indicates how quickly the system begins responding after a user stops speaking.
3. TTFB (Time to First Byte):
   Time elapsed from the start of a request to receiving the first byte of the response, typically used to measure the responsiveness of the backend or LLM.
4. Total Latency:
   Cumulative time from when the user finishes speaking to when a complete response is delivered, including EOU detection, STT, LLM processing, and TTS if used.
5. TTS Processing Time:
   Time taken to convert the generated text response into speech.
6. User Speech Duration:
   The total duration of the user’s spoken input, useful for correlating latency with input length.
7. Total Latency:
   End-to-end time from when the user finishes speaking to when the spoken response is fully delivered.

==> Each session's metrics are saved in .xlxs file, to view them open 'Metrics' directory.
