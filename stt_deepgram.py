import os
import io
from deepgram import DeepgramClient, PrerecordedOptions

# Load API key
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

if not DEEPGRAM_API_KEY:
    raise ValueError("Deepgram API key is missing. Set DEEPGRAM_API_KEY as an environment variable.")

# Initialize Deepgram client
deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)

def transcribe_audio(audio_bytes, model="nova-2") -> str:
    """
    Transcribes audio using Deepgram API.

    :param audio_bytes: Audio file as BytesIO or bytes
    :param model: Deepgram model to use (nova-2 or nova-3)
    :return: Transcribed text or an error message
    """
    try:
        # Validate model selection
        if model not in ["nova-2", "nova-3"]:
            model = "nova-2"  # Default to nova-2 if invalid

        # Configure options for English transcription
        options = PrerecordedOptions(
            model=model,
            smart_format=True,
            punctuate=True,
            language="en-US"
        )

        # Reset file pointer if it's a BytesIO object
        if hasattr(audio_bytes, 'seek'):
            audio_bytes.seek(0)
            
        # Get the actual bytes depending on the input type
        audio_data = audio_bytes.getvalue() if isinstance(audio_bytes, io.BytesIO) else audio_bytes
        
        # Prepare payload and send to Deepgram
        payload = {'buffer': audio_data, 'mimetype': 'audio/wav'}
        response = deepgram.listen.rest.v("1").transcribe_file(payload, options)
        
        # Extract transcript
        transcript = response.results.channels[0].alternatives[0].transcript
        return transcript if transcript else "No speech detected."

    except Exception as e:
        return f"Error in Deepgram STT: {str(e)}"