# =============================================================================
# AUDIO MODULE - Sound Manager
# File: modules/audio/sound_manager.py
# =============================================================================

import pygame
import numpy as np
import threading
import time
import logging

logger = logging.getLogger(__name__)

class SoundManager:
    """Manages sound effects with proper initialization"""

    def __init__(self, config_manager):
        self.config = config_manager
        self.sounds = {}
        self.initialized = False
        self.volume = self.config.get('sounds.volume', 0.7)
        self._init_lock = threading.Lock()
        self.initialize_audio()

    def initialize_audio(self):
        """Initialize pygame mixer with error handling"""
        with self._init_lock:
            if self.initialized:
                return

            try:
                pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
                pygame.mixer.init()
                self.initialized = True
                self.create_sounds()
                logger.info("Sound system initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing sound system: {e}")
                self.initialized = False

    def create_sounds(self):
        """Create sound effects"""
        if not self.initialized:
            return

        try:
            sample_rate = 22050
            duration = 0.3

            # Start recording sound (ascending beep)
            t = np.linspace(0, duration, int(sample_rate * duration))
            start_freq = np.linspace(600, 800, len(t))
            start_tone = np.sin(2 * np.pi * start_freq * t) * self.volume
            start_sound = np.array([start_tone, start_tone]).T
            self.sounds['start'] = pygame.sndarray.make_sound((start_sound * 32767).astype(np.int16))

            # Stop recording sound (descending beep)
            stop_freq = np.linspace(800, 600, len(t))
            stop_tone = np.sin(2 * np.pi * stop_freq * t) * self.volume
            stop_sound = np.array([stop_tone, stop_tone]).T
            self.sounds['stop'] = pygame.sndarray.make_sound((stop_sound * 32767).astype(np.int16))

            # Wake word sound (chime sequence)
            chime_duration = 0.8
            t_chime = np.linspace(0, chime_duration, int(sample_rate * chime_duration))
            chime_freqs = [523, 659, 784]  # C, E, G
            chime_sound = np.zeros((len(t_chime), 2))

            for i, freq in enumerate(chime_freqs):
                start_idx = int(i * len(t_chime) / 3)
                end_idx = int((i + 1) * len(t_chime) / 3)
                segment_len = end_idx - start_idx
                t_segment = np.linspace(0, chime_duration/3, segment_len)

                tone = np.sin(2 * np.pi * freq * t_segment) * self.volume * np.exp(-t_segment * 2)
                chime_sound[start_idx:end_idx, 0] = tone
                chime_sound[start_idx:end_idx, 1] = tone

            self.sounds['wake_word'] = pygame.sndarray.make_sound((chime_sound * 32767).astype(np.int16))

            logger.info("Sound effects created successfully")

        except Exception as e:
            logger.error(f"Error creating sounds: {e}")

    def play_sound(self, sound_type):
        """Play sound effect with threading"""
        def _play():
            try:
                if not self.config.get('sounds.enabled', True):
                    return

                if not self.config.get(f'sounds.{sound_type}', True):
                    return

                if not self.initialized:
                    self.initialize_audio()

                if sound_type in self.sounds:
                    self.sounds[sound_type].play()
                    logger.debug(f"Played sound: {sound_type}")

            except Exception as e:
                logger.error(f"Error playing sound {sound_type}: {e}")

        # Play sound in separate thread to avoid blocking
        threading.Thread(target=_play, daemon=True).start()
