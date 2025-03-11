import os
from io import BytesIO
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

def transcribe_audio(audio_bytes: BytesIO) -> str:
    """
    Sends audio data to ElevenLabs API and returns the transcribed text.

    :param audio_bytes: BytesIO object containing audio data
    :return: Transcribed text
    """
    try:
        transcription = client.speech_to_text.convert(
            file=audio_bytes,
            model_id="scribe_v1_base",  # Options: "scribe_v1" or "scribe_v1_base"
            tag_audio_events=False,  # Detect sounds like laughter, applause, etc.
            language_code="en"  # Auto-detect if set to None
        )
        return transcription.text

    except Exception as e:
        return f"Error in stt_eleven_labs: {str(e)}"