# =============================================================================
# FEATURES MODULE - Push to Talk
# File: modules/features/push_to_talk.py
# =============================================================================

import logging
from pynput import keyboard
from pynput.keyboard import Key, Listener as KeyboardListener

logger = logging.getLogger(__name__)

class PushToTalkHandler:
    """Handles push-to-talk functionality"""

    def __init__(self, config_manager, callback_handler):
        self.config = config_manager
        self.callback_handler = callback_handler
        self.is_active = False
        self.current_keys = set()
        self.enabled = True

    def check_activation(self, pressed_keys):
        """Check if push-to-talk keys are pressed"""
        if not self.enabled:
            return False

        ptt_keys = set([k.lower().strip() for k in self.config.get('hotkeys.push_to_talk', [])])
        current_keys_normalized = set([k.lower().strip() for k in pressed_keys])

        should_activate = ptt_keys and ptt_keys.issubset(current_keys_normalized)

        if should_activate and not self.is_active:
            self.is_active = True
            logger.info("Push-to-talk activated")
            self.callback_handler.on_push_to_talk_start()
            return True
        elif not should_activate and self.is_active:
            self.is_active = False
            logger.info("Push-to-talk deactivated")
            self.callback_handler.on_push_to_talk_end()
            return True

        return False

    def reset(self):
        """Reset push-to-talk state"""
        if self.is_active:
            self.is_active = False
            self.callback_handler.on_push_to_talk_end()
