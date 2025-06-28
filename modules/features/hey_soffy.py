# =============================================================================
# FEATURES MODULE - Hey Soffy Voice Assistant
# File: modules/features/hey_soffy.py
# =============================================================================

import threading
import time
import queue
import pyaudio
import numpy as np
import logging

logger = logging.getLogger(__name__)

class HeySoffyHandler:
    """Handles Hey Soffy voice assistant functionality"""

    def __init__(self, config_manager, whisper_model, sound_manager, callback_handler):
        self.config = config_manager
        self.whisper_model = whisper_model
        self.sound_manager = sound_manager
        self.callback_handler = callback_handler
        self.is_listening = False
        self.wake_word = self.config.get('voice_assistant.wake_word', 'hey soffy').lower()
        self.sensitivity = self.config.get('voice_assistant.sensitivity', 0.5)
        self.buffer_duration = 3.0
        self.sample_rate = self.config.get('audio.sample_rate', 16000)
        self.audio_buffer = []
        self.buffer_lock = threading.Lock()
        self.audio = None
        self.stream = None
        self.listen_thread = None
        self.last_detection_time = 0
        self.cooldown_period = 3.0  # seconds between detections

    def start_listening(self):
        """Start listening for wake word"""
        if not self.config.get('voice_assistant.enabled', True):
            logger.info("Voice assistant disabled in config")
            return

        if self.is_listening:
            logger.warning("Already listening for wake word")
            return

        self.is_listening = True
        self.listen_thread = threading.Thread(target=self._listen_worker, daemon=True)
        self.listen_thread.start()
        logger.info("Hey Soffy listening started")

    def stop_listening(self):
        """Stop listening for wake word"""
        self.is_listening = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass
        logger.info("Hey Soffy listening stopped")

    def _listen_worker(self):
        """Worker thread for wake word detection"""
        try:
            self.audio = pyaudio.PyAudio()

            self.stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=1024,
                input_device_index=self.config.get('audio.device_index')
            )

            self.stream.start_stream()

            while self.is_listening:
                try:
                    data = self.stream.read(1024, exception_on_overflow=False)
                    audio_chunk = np.frombuffer(data, dtype=np.float32)

                    with self.buffer_lock:
                        self.audio_buffer.extend(audio_chunk)
                        # Keep only last N seconds
                        max_samples = int(self.buffer_duration * self.sample_rate)
                        if len(self.audio_buffer) > max_samples:
                            self.audio_buffer = self.audio_buffer[-max_samples:]

                    # Check for voice activity and wake word
                    if self._detect_voice_activity(audio_chunk):
                        current_time = time.time()
                        if current_time - self.last_detection_time > self.cooldown_period:
                            if self._check_for_wake_word():
                                self.last_detection_time = current_time
                                self._on_wake_word_detected()

                    time.sleep(0.01)  # Small delay

                except Exception as e:
                    logger.error(f"Error in wake word listening: {e}")
                    time.sleep(0.1)

        except Exception as e:
            logger.error(f"Error setting up wake word listener: {e}")
        finally:
            self._cleanup_audio()

    def _cleanup_audio(self):
        """Cleanup audio resources"""
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            if self.audio:
                self.audio.terminate()
                self.audio = None
        except Exception as e:
            logger.error(f"Error during audio cleanup: {e}")

    def _detect_voice_activity(self, audio_chunk):
        """Simple voice activity detection"""
        rms = np.sqrt(np.mean(audio_chunk**2))
        threshold = self.config.get('audio.voice_activation_threshold', 0.02)
        return rms > threshold

    def _check_for_wake_word(self):
        """Check if wake word is present in audio buffer"""
        try:
            with self.buffer_lock:
                if len(self.audio_buffer) < self.sample_rate:
                    return False
                audio_data = np.array(self.audio_buffer[-int(self.sample_rate * 2.5):], dtype=np.float32)

            # Normalize audio
            if np.max(np.abs(audio_data)) > 0:
                audio_data = audio_data / np.max(np.abs(audio_data))

            # Quick transcription
            result = self.whisper_model.transcribe(
                audio_data,
                task="transcribe",
                language="en",
                fp16=False,
                temperature=0,
                best_of=1,
                beam_size=1
            )

            text = result['text'].lower().strip()
            logger.debug(f"Wake word check: '{text}'")

            # Check for wake word
            wake_words = self.wake_word.split()
            text_words = text.split()

            # Look for consecutive wake words in the text
            for i in range(len(text_words) - len(wake_words) + 1):
                if text_words[i:i+len(wake_words)] == wake_words:
                    logger.info(f"Wake word detected in: '{text}'")
                    return True

        except Exception as e:
            logger.error(f"Error checking wake word: {e}")

        return False

    def _on_wake_word_detected(self):
        """Handle wake word detection"""
        logger.info("Hey Soffy activated!")
        self.sound_manager.play_sound('wake_word')

        # Brief pause before starting recording
        time.sleep(0.3)

        # Trigger voice assistant recording
        self.callback_handler.on_voice_assistant_activated()
