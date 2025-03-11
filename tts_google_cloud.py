import base64
from google.cloud import texttospeech

# Initialize the Google Cloud TTS client
tts_client = texttospeech.TextToSpeechClient()

def text_to_speech(text: str, language_code="en-IN", gender="MALE", audio_encoding="MP3") -> str:
    """
    Converts input text to speech using Google Cloud TTS.
    Returns the resulting audio content as a base64-encoded string.
    Defaults to Tamil (ta-IN) with a male voice.
    """
    try:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Map gender input to enum
        if gender.upper() == "MALE":
            ssml_gender = texttospeech.SsmlVoiceGender.MALE
        elif gender.upper() == "FEMALE":
            ssml_gender = texttospeech.SsmlVoiceGender.FEMALE
        else:
            ssml_gender = texttospeech.SsmlVoiceGender.NEUTRAL

        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=ssml_gender
        )

        # Set audio encoding
        if audio_encoding.upper() == "MP3":
            audio_enc = texttospeech.AudioEncoding.MP3
        elif audio_encoding.upper() == "OGG_OPUS":
            audio_enc = texttospeech.AudioEncoding.OGG_OPUS
        else:
            audio_enc = texttospeech.AudioEncoding.MP3

        audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_enc
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