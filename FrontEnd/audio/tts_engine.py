import pyttsx3
import logging
import os
import re
import threading
from gtts import gTTS
import pygame

# Suppress pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

class TTSEngine:
    def __init__(self):
        self.logger = logging.getLogger("TTSEngine")
        try:
            self.engine = pyttsx3.init('sapi5')
        except:
            self.engine = pyttsx3.init()
            
        self.found_ar = False
        self._setup_voice()
        
        # Initialize pygame mixer for fallback
        pygame.mixer.init()

    def _setup_voice(self):
        """Try to set an Arabic voice if available, else use default."""
        voices = self.engine.getProperty('voices')
        self.found_ar = False
        
        for voice in voices:
            v_lower = voice.name.lower()
            if any(kw in v_lower for kw in ['arabic', 'عربي', 'hoda', 'naay', 'laila', 'zira']):
                self.engine.setProperty('voice', voice.id)
                if any(kw in v_lower for kw in ['arabic', 'عربي', 'hoda', 'naay', 'laila']):
                    self.found_ar = True
                break
        
        self.engine.setProperty('rate', 160)
        self.engine.setProperty('volume', 1.0)

    def say(self, text):
        # Clean text
        clean_text = re.sub(r'[^\w\s.,!؟?()\'"-]', '', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        if not clean_text:
            return

        if self.found_ar or not any('\u0600' <= c <= '\u06FF' for c in clean_text):
            # Use Local Engine if Arabic is supported or text is English
            self.logger.info(f"Speaking via Local TTS: {clean_text}")
            self.engine.say(clean_text)
        else:
            # FALLBACK: Use gTTS for Arabic if local voice is missing
            self.logger.info(f"Speaking via gTTS Fallback: {clean_text}")
            threading.Thread(target=self._speak_gtts, args=(clean_text,), daemon=True).start()

    def _speak_gtts(self, text):
        try:
            temp_file = "temp_speech.mp3"
            tts = gTTS(text=text, lang='ar')
            tts.save(temp_file)
            
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            pygame.mixer.music.unload()
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
        except Exception as e:
            self.logger.error(f"gTTS Fallback Error: {e}")

    def runAndWait(self):
        try:
            self.engine.runAndWait()
        except:
            pass

    def stop(self):
        self.engine.stop()
        pygame.mixer.music.stop()
