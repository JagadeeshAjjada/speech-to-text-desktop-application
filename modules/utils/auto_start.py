# =============================================================================
# UTILS MODULE - Auto Start Manager
# File: modules/utils/auto_start.py
# =============================================================================

import winreg
import sys
import os
import logging

logger = logging.getLogger(__name__)

class AutoStartManager:
    """Windows auto-start management"""

    def __init__(self, app_name="VoiceType Pro"):
        self.app_name = app_name
        self.registry_key = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def is_auto_start_enabled(self):
        """Check if auto-start is enabled"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_key) as key:
                try:
                    winreg.QueryValueEx(key, self.app_name)
                    return True
                except FileNotFoundError:
                    return False
        except Exception as e:
            logger.error(f"Error checking auto-start: {e}")
            return False

    def enable_auto_start(self):
        """Enable auto-start"""
        try:
            exe_path = sys.executable
            if exe_path.endswith("python.exe"):
                script_path = os.path.abspath(__file__)
                exe_path = f'"{exe_path}" "{script_path}"'
            else:
                exe_path = f'"{exe_path}"'

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, exe_path)

            logger.info("Auto-start enabled")
            return True
        except Exception as e:
            logger.error(f"Error enabling auto-start: {e}")
            return False

    def disable_auto_start(self):
        """Disable auto-start"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_key, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, self.app_name)
                    logger.info("Auto-start disabled")
                    return True
                except FileNotFoundError:
                    return True
        except Exception as e:
            logger.error(f"Error disabling auto-start: {e}")
            return False
