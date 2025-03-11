import os
from io import BytesIO
from deepgram import DeepgramClient, PrerecordedOptions

# Load API key
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

if not DEEPGRAM_API_KEY:
    raise ValueError("Deepgram API key is missing. Set DEEPGRAM_API_KEY as an environment variable.")

# Initialize Deepgram client
deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)

def transcribe_audio(audio_bytes: BytesIO) -> str:
    """
    Transcribes audio using Deepgram API.

    :param audio_bytes: Audio file as BytesIO
    :param language: Language code (default: Tamil 'ta-IN')
    :return: Transcribed text or an error message
    """
    try:
        options = PrerecordedOptions(
            model="whisper-large",  # Use Deepgram's latest stable STT model
            language='en',  # Tamil: 'ta-IN', English: 'en-US'
            smart_format=True,
            punctuate=True,
        )

        # Reset file pointer
        audio_bytes.seek(0)

        # Transcribe the audio
        response = deepgram.listen.prerecorded.v("1").transcribe_file(
            {"buffer": audio_bytes, "mimetype": "audio/wav"},  # Ensure correct MIME type
            options
        )

        # Extract transcript
        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        return transcript if transcript else "No speech detected."

    except Exception as e:
        return f"Error in Deepgram STT: {str(e)}"