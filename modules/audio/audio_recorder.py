# =============================================================================
# AUDIO MODULE - Audio Recorder
# File: modules/audio/audio_recorder.py
# =============================================================================

import pyaudio
import numpy as np
import threading
import time
import logging

logger = logging.getLogger(__name__)

class AudioRecorder:
    """Enhanced audio recorder with proper callback handling"""

    def __init__(self, config_manager, sound_manager):
        self.config = config_manager
        self.sound_manager = sound_manager
        self.is_recording = False
        self.sample_rate = self.config.get('audio.sample_rate', 16000)
        self.channels = self.config.get('audio.channels', 1)
        self.chunk_size = self.config.get('audio.chunk_size', 1024)
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.audio_data = []
        self.silence_start = None
        self.silence_timeout = self.config.get('audio.silence_timeout', 2.0)
        self.auto_stop_callback = None
        self.auto_stop_enabled = False
        self._record_lock = threading.Lock()

    def start_recording(self, auto_stop=False):
        """Start recording with proper locking"""
        with self._record_lock:
            if self.is_recording:
                logger.warning("Already recording")
                return False

            try:
                self.is_recording = True
                self.auto_stop_enabled = auto_stop
                self.audio_data = []
                self.silence_start = None

                self.stream = self.audio.open(
                    format=pyaudio.paFloat32,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk_size,
                    input_device_index=self.config.get('audio.device_index'),
                    stream_callback=self._audio_callback
                )

                self.stream.start_stream()
                self.sound_manager.play_sound('start')
                logger.info(f"Recording started (auto_stop: {auto_stop})")
                return True

            except Exception as e:
                logger.error(f"Error starting recording: {e}")
                self.is_recording = False
                return False

    def stop_recording(self):
        """Stop recording with proper cleanup"""
        with self._record_lock:
            if not self.is_recording:
                return None

            try:
                self.is_recording = False
                self.auto_stop_enabled = False

                if self.stream:
                    self.stream.stop_stream()
                    self.stream.close()
                    self.stream = None

                self.sound_manager.play_sound('stop')

                if self.audio_data:
                    audio_array = np.concatenate(self.audio_data)
                    logger.info(f"Recording stopped, captured {len(audio_array)} samples")
                    return audio_array

            except Exception as e:
                logger.error(f"Error stopping recording: {e}")

            return None

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Audio callback with auto-stop detection"""
        if not self.is_recording:
            return (in_data, pyaudio.paComplete)

        try:
            audio_chunk = np.frombuffer(in_data, dtype=np.float32)
            self.audio_data.append(audio_chunk)

            # Auto-stop detection
            if self.auto_stop_enabled and self.auto_stop_callback:
                rms = np.sqrt(np.mean(audio_chunk**2))
                threshold = self.config.get('audio.voice_activation_threshold', 0.02)

                if rms < threshold:
                    if self.silence_start is None:
                        self.silence_start = time.time()
                    elif time.time() - self.silence_start > self.silence_timeout:
                        # Trigger auto-stop in main thread
                        threading.Timer(0.01, self._trigger_auto_stop).start()
                        return (in_data, pyaudio.paComplete)
                else:
                    self.silence_start = None

        except Exception as e:
            logger.error(f"Error in audio callback: {e}")

        return (in_data, pyaudio.paContinue)

    def _trigger_auto_stop(self):
        """Trigger auto-stop from callback"""
        if self.auto_stop_callback:
            self.auto_stop_callback()

    def get_audio_devices(self):
        """Get available audio devices"""
        devices = []
        try:
            for i in range(self.audio.get_device_count()):
                info = self.audio.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    devices.append({
                        'index': i,
                        'name': info['name'],
                        'channels': info['maxInputChannels']
                    })
        except Exception as e:
            logger.error(f"Error getting audio devices: {e}")
        return devices

    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.is_recording:
                self.stop_recording()
            if self.stream:
                self.stream.close()
            self.audio.terminate()
        except Exception as e:
            logger.error(f"Error during audio cleanup: {e}")
