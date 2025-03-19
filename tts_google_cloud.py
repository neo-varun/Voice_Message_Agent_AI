import base64
from google.cloud import texttospeech

# Initialize the Google Cloud TTS client
tts_client = texttospeech.TextToSpeechClient()

# Define specific voice names for English
LANGUAGE_VOICES = {
    'en-US': ['en-US-Chirp3-HD-Orus', 'en-US-Chirp3-HD-Aoede'],
}

GENDER_INDICES = {
    'MALE': 0,
    'FEMALE': 1
}

def text_to_speech(text: str, language_code="en-US", voice_gender="FEMALE", audio_encoding="MP3") -> str:
    """
    Converts input text to speech using Google Cloud TTS with specific voice names.
    Returns the resulting audio content as a base64-encoded string.
    
    :param text: Text to convert to speech
    :param language_code: Language code (only en-US supported)
    :param voice_gender: Gender of voice (MALE or FEMALE)
    :param audio_encoding: Audio encoding format (MP3 or OGG_OPUS)
    :return: Base64-encoded audio or error message
    """
    try:
        # Ensure the language code is supported, default to en-US if not
        language_code = language_code if language_code in LANGUAGE_VOICES else "en-US"
        
        # Get the voice index based on gender preference
        voice_index = GENDER_INDICES.get(voice_gender.upper(), 0)
        
        # Get the specific voice name
        voice_name = LANGUAGE_VOICES[language_code][voice_index]
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Use named voice instead of just gender
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )

        # Set audio encoding
        if audio_encoding.upper() == "MP3":
            audio_enc = texttospeech.AudioEncoding.MP3
        elif audio_encoding.upper() == "OGG_OPUS":
            audio_enc = texttospeech.AudioEncoding.OGG_OPUS
        else:
            audio_enc = texttospeech.AudioEncoding.MP3

        audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_enc,
            speaking_rate=1.0,
            pitch=0.0,
            volume_gain_db=0.0
        )

        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # Return the audio content encoded in base64 so it can be sent in JSON
        return base64.b64encode(response.audio_content).decode('utf-8')
    
    except Exception as e:
        return f"Error in tts_google_cloud: {str(e)}"