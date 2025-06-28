# =============================================================================
# CORE MODULE - Whisper Transcriber
# File: modules/core/whisper_transcriber.py
# =============================================================================

import whisper
import numpy as np
import logging

logger = logging.getLogger(__name__)

class WhisperTranscriber:
    """Optimized Whisper transcriber"""

    def __init__(self, config_manager):
        self.config = config_manager
        self.model = None
        self.model_size = self.config.get('whisper.model_size', 'base')
        self.language = self.config.get('whisper.language', 'auto')
        self.task = self.config.get('whisper.task', 'transcribe')
        self.load_model()

    def load_model(self):
        """Load Whisper model"""
        try:
            logger.info(f"Loading Whisper model: {self.model_size}")
            self.model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}")
            raise

    def transcribe(self, audio_data, language=None):
        """Transcribe audio data"""
        if self.model is None:
            raise Exception("Whisper model not loaded")

        try:
            # Prepare audio
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            # Normalize
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = audio_data / max_val

            # Language setting
            lang = language or (None if self.language == 'auto' else self.language)

            # Transcribe with optimized settings
            result = self.model.transcribe(
                audio_data,
                language=lang,
                task=self.task,
                fp16=False,
                temperature=0.0,
                best_of=1,
                beam_size=1,
                no_speech_threshold=0.6,
                logprob_threshold=-1.0
            )

            text = result['text'].strip()
            text = self._post_process_text(text)

            logger.info(f"Transcription completed: {text[:50]}...")
            return text

        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return None

    def _post_process_text(self, text):
        """Enhanced text post-processing"""
        if not text:
            return text

        # Remove filler words
        if self.config.get('behavior.remove_filler_words', True):
            filler_words = ['um', 'uh', 'er', 'ah', 'hmm', 'like', 'you know']
            words = text.split()
            words = [word for word in words if word.lower() not in filler_words]
            text = ' '.join(words)

        # Capitalize sentences
        if self.config.get('behavior.capitalize_sentences', True):
            sentences = text.split('. ')
            sentences = [s.strip().capitalize() for s in sentences if s.strip()]
            text = '. '.join(sentences)

        # Auto punctuation
        if self.config.get('behavior.auto_punctuation', True):
            if text and not text.endswith(('.', '!', '?')):
                text += '.'

        return text
