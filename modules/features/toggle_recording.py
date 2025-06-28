# =============================================================================
# FEATURES MODULE - Toggle Recording
# File: modules/features/toggle_recording.py
# =============================================================================

import time
import logging

logger = logging.getLogger(__name__)

class ToggleRecordingHandler:
    """Handles toggle recording functionality"""

    def __init__(self, config_manager, callback_handler):
        self.config = config_manager
        self.callback_handler = callback_handler
        self.last_toggle_time = 0
        self.enabled = True
        self.debounce_delay = 0.5  # seconds

    def check_activation(self, pressed_keys):
        """Check if toggle recording keys are pressed"""
        if not self.enabled:
            return False

        toggle_keys = set([k.lower().strip() for k in self.config.get('hotkeys.toggle_recording', [])])
        current_keys_normalized = set([k.lower().strip() for k in pressed_keys])

        current_time = time.time()

        if (toggle_keys and toggle_keys.issubset(current_keys_normalized) and
            current_time - self.last_toggle_time > self.debounce_delay):

            self.last_toggle_time = current_time
            logger.info("Toggle recording activated")
            self.callback_handler.on_toggle_recording()
            return True

        return False
