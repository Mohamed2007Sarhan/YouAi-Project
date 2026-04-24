import speech_recognition as sr
from PyQt6.QtCore import QThread, pyqtSignal
import time

class SpeechEngine(QThread):
    # Signals to communicate with the main GUI thread
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()
    speech_recognized = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, language="ar-EG"):
        super().__init__()
        self.language = language
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_running = True
        self.stop_listening_func = None

        # Adjust for ambient noise with longer duration for better sensitivity
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
        self.recognizer.dynamic_energy_threshold = True

    def set_language(self, language: str):
        """Update the recognition language dynamically."""
        self.language = language

    def callback(self, recognizer, audio):
        try:
            self.listening_stopped.emit() # Speech ended, now recognizing
            
            # Use Google Web Speech API with the specified language
            text = recognizer.recognize_google(audio, language=self.language)
            self.speech_recognized.emit(text)
            
        except sr.UnknownValueError:
            # Could not understand audio
            pass 
        except sr.RequestError as e:
            self.error_occurred.emit(f"API Error: {e}")
        finally:
            self.listening_started.emit() # Resume visual listening state

    def run(self):
        self.listening_started.emit()
        # listen_in_background spins up its own thread for audio listening
        self.stop_listening_func = self.recognizer.listen_in_background(
            self.microphone, 
            self.callback,
            phrase_time_limit=15 # Increased for complex Arabic sentences
        )

        # Keep the QThread alive while running
        while self.is_running:
            time.sleep(0.1)

    def stop(self):
        self.is_running = False
        if self.stop_listening_func:
            self.stop_listening_func(wait_for_stop=False)
