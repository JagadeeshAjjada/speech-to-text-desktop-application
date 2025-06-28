# =============================================================================
# CORE MODULE - Hotkey Manager
# File: modules/core/hotkey_manager.py
# =============================================================================

from pynput import keyboard
from pynput.keyboard import Key, Listener as KeyboardListener
import logging
# Import feature handlers
from ..features.push_to_talk import PushToTalkHandler
from ..features.toggle_recording import ToggleRecordingHandler

logger = logging.getLogger(__name__)

class HotkeyManager:
    """Enhanced hotkey manager with modular handlers"""

    def __init__(self, config_manager, callback_handler):
        self.config = config_manager
        self.callback_handler = callback_handler
        self.keyboard_listener = None
        self.current_keys = set()
        self.enabled = True

        self.push_to_talk = PushToTalkHandler(config_manager, callback_handler)
        self.toggle_recording = ToggleRecordingHandler(config_manager, callback_handler)

        self.start_listening()

    def start_listening(self):
        """Start listening for hotkeys"""
        try:
            self.keyboard_listener = KeyboardListener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
                suppress=False
            )
            self.keyboard_listener.start()
            logger.info("Hotkey listener started")
        except Exception as e:
            logger.error(f"Error starting hotkey listener: {e}")

    def stop_listening(self):
        """Stop listening for hotkeys"""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        logger.info("Hotkey listener stopped")

    def update_hotkeys(self):
        """Update hotkeys from config"""
        logger.info("Hotkeys updated from config")

    def _on_key_press(self, key):
        """Handle key press events"""
        if not self.enabled:
            return

        try:
            key_name = self._get_key_name(key)
            if key_name:
                self.current_keys.add(key_name)
                logger.debug(f"Key pressed: {key_name}, Current: {self.current_keys}")

                # Check both handlers
                self.push_to_talk.check_activation(self.current_keys)
                self.toggle_recording.check_activation(self.current_keys)

        except Exception as e:
            logger.error(f"Error handling key press: {e}")

    def _on_key_release(self, key):
        """Handle key release events"""
        if not self.enabled:
            return

        try:
            key_name = self._get_key_name(key)
            if key_name:
                self.current_keys.discard(key_name)
                logger.debug(f"Key released: {key_name}, Current: {self.current_keys}")

                # Check push-to-talk release
                self.push_to_talk.check_activation(self.current_keys)

        except Exception as e:
            logger.error(f"Error handling key release: {e}")

    def _get_key_name(self, key):
        """Get standardized key name"""
        try:
            if hasattr(key, 'char') and key.char and key.char.isprintable():
                return key.char.lower()
            elif hasattr(key, 'name'):
                name_mapping = {
                    'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
                    'alt_l': 'alt', 'alt_r': 'alt',
                    'shift_l': 'shift', 'shift_r': 'shift',
                    'cmd': 'win', 'cmd_l': 'win', 'cmd_r': 'win',
                    'win': 'win', 'win_l': 'win', 'win_r': 'win'
                }
                key_name = key.name.lower()
                return name_mapping.get(key_name, key_name)
            else:
                return str(key).lower().replace('key.', '').replace('<', '').replace('>', '')
        except Exception:
            return None
