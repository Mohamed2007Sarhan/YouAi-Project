"""
Speech input (microphone → text) for voice-only UI.
Uses SpeechRecognition + PyAudio when installed.
"""

import os
import sys
from typing import Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLIC_APIS = os.path.join(PROJECT_ROOT, "Public Apis")
if PUBLIC_APIS not in sys.path:
    sys.path.insert(0, PUBLIC_APIS)


def transcribe_microphone(
    phrase_time_limit: int = 25,
    language: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Record from default microphone and return transcribed text.
    language: e.g. 'en-US', 'ar-EG' — passed to Google recognizer if set.
    Returns (ok, text_or_error_message).
    """
    try:
        import speech_recognition as sr
    except ImportError:
        return False, (
            "SpeechRecognition is not installed. Install with: pip install SpeechRecognition"
        )

    try:
        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.4)
            audio = r.listen(source, timeout=8, phrase_time_limit=phrase_time_limit)
    except ImportError:
        return False, (
            "PyAudio is required for the microphone. Install with: pip install pyaudio"
        )
    except Exception as e:
        return False, f"Microphone error: {e}"

    try:
        kwargs = {}
        if language:
            kwargs["language"] = language
        text = r.recognize_google(audio, **kwargs)
        return True, (text or "").strip()
    except sr.UnknownValueError:
        return False, "Could not understand audio. Try again."
    except sr.RequestError as e:
        return False, f"Speech service error: {e}"
