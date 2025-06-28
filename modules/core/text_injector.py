# =============================================================================
# CORE MODULE - Text Injector
# File: modules/core/text_injector.py
# =============================================================================

import pyperclip
import time
import threading
from pynput import keyboard
from pynput.keyboard import Key
import logging

logger = logging.getLogger(__name__)

class TextInjector:
    """Optimized text injection"""

    def __init__(self):
        self.controller = keyboard.Controller()

    def paste_text(self, text):
        """Paste text at cursor position"""
        try:
            # Store original clipboard
            original_clipboard = ""
            try:
                original_clipboard = pyperclip.paste()
            except:
                pass

            # Copy new text
            pyperclip.copy(text)
            time.sleep(0.05)

            # Paste using Ctrl+V
            with self.controller.pressed(Key.ctrl):
                self.controller.press('v')
                self.controller.release('v')

            # Restore clipboard after delay
            def restore_clipboard():
                time.sleep(0.5)
                try:
                    pyperclip.copy(original_clipboard)
                except:
                    pass

            threading.Timer(0.5, restore_clipboard).start()
            logger.info(f"Text pasted: {text[:50]}...")

        except Exception as e:
            logger.error(f"Error pasting text: {e}")
            # Fallback to typing
            try:
                self.controller.type(text)
            except Exception as e2:
                logger.error(f"Error typing text: {e2}")
