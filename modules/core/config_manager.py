# =============================================================================
# CORE MODULE - Configuration Manager
# File: modules/core/config_manager.py
# =============================================================================

import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration and settings"""

    def __init__(self):
        self.config_file = Path.home() / ".voicetype_pro" / "config.json"
        self.config_file.parent.mkdir(exist_ok=True)
        self.default_config = {
            "hotkeys": {
                "push_to_talk": ["ctrl", "space"],
                "toggle_recording": ["ctrl", "shift", "r"]
            },
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
                "device_index": None,
                "voice_activation_threshold": 0.02,
                "silence_timeout": 2.0
            },
            "whisper": {
                "model_size": "base",
                "language": "auto",
                "task": "transcribe"
            },
            "voice_assistant": {
                "enabled": True,
                "wake_word": "hey soffy",
                "sensitivity": 0.5,
                "auto_stop_timeout": 3.0,
                "continuous_listening": True
            },
            "ui": {
                "theme": "dark",
                "minimize_to_tray": True,
                "show_notifications": True,
                "auto_start": False
            },
            "behavior": {
                "auto_punctuation": True,
                "capitalize_sentences": True,
                "remove_filler_words": True,
                "confidence_threshold": 0.7
            },
            "sounds": {
                "enabled": True,
                "start_recording": True,
                "stop_recording": True,
                "wake_word_detected": True,
                "volume": 0.7
            }
        }
        self.load_config()

    def load_config(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    self.config = self._deep_merge(self.default_config, loaded_config)
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config = self.default_config.copy()

    def _deep_merge(self, default, loaded):
        """Deep merge configurations"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get(self, key_path, default=None):
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            value = value.get(key, default)
            if value is None:
                return default
        return value

    def set(self, key_path, value):
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            config = config.setdefault(key, {})
        config[keys[-1]] = value
        self.save_config()
