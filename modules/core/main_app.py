# =============================================================================
# CORE MODULE - Main Application
# File: modules/core/main_app.py
# =============================================================================

import customtkinter as ctk
import threading
import time
import logging
import sys
from pathlib import Path
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
# Initialize configuration first
from ..core.config_manager import ConfigManager
# Initialize audio components
from ..audio.sound_manager import SoundManager
from ..audio.audio_recorder import AudioRecorder
# Initialize core components
from ..core.whisper_transcriber import WhisperTranscriber
from ..core.text_injector import TextInjector
# Initialize feature handlers
from ..core.hotkey_manager import HotkeyManager
from ..features.hey_soffy import HeySoffyHandler
# Initialize UI components
from ..ui.main_window import MainWindow
from ..ui.background_popup import BackgroundPopup
from ..utils.auto_start import AutoStartManager
from ..ui.settings_window import SettingsWindow

logger = logging.getLogger(__name__)

class VoiceTypeProApp:
    """Main application with fixed functionality"""

    def __init__(self):

        self.config = ConfigManager()

        self.sound_manager = SoundManager(self.config)
        self.audio_recorder = AudioRecorder(self.config, self.sound_manager)

        self.transcriber = WhisperTranscriber(self.config)
        self.text_injector = TextInjector()

        self.hotkey_manager = HotkeyManager(self.config, self)
        self.hey_soffy = HeySoffyHandler(self.config, self.transcriber.model, self.sound_manager, self)

        self.main_window = MainWindow(self.config, self)
        self.background_popup = BackgroundPopup(self)
        self.auto_start_manager = AutoStartManager()

        # Application state
        self.is_recording = False
        self.is_toggle_mode = False
        self.background_mode = False
        self.tray_icon = None

        # Set up audio recorder callback
        self.audio_recorder.auto_stop_callback = self._on_auto_stop_triggered

        # Setup system tray
        self.setup_tray()

        # Start voice assistant
        if self.config.get('voice_assistant.enabled', True):
            self.hey_soffy.start_listening()

    def setup_tray(self):
        """Setup system tray"""
        try:
            # Create icon
            image = Image.new('RGB', (64, 64), color='blue')
            draw = ImageDraw.Draw(image)
            draw.ellipse([16, 16, 48, 48], fill='white')

            menu = pystray.Menu(
                item('Show', self.show_window),
                item('Background Mode', self.toggle_background_mode),
                item('Settings', self.open_settings),
                pystray.Menu.SEPARATOR,
                item('Exit', self.quit_application)
            )

            self.tray_icon = pystray.Icon("VoiceType Pro", image, menu=menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

        except Exception as e:
            logger.error(f"Error setting up tray: {e}")

    # Callback methods for features
    def on_push_to_talk_start(self):
        """Handle push-to-talk activation"""
        logger.info("Push-to-talk start callback")
        if not self.is_recording:
            self.start_recording()

    def on_push_to_talk_end(self):
        """Handle push-to-talk deactivation"""
        logger.info("Push-to-talk end callback")
        if self.is_recording and not self.is_toggle_mode:
            self.stop_recording_and_transcribe()

    def on_toggle_recording(self):
        """Handle toggle recording"""
        logger.info("Toggle recording callback")
        self.toggle_recording()

    def on_voice_assistant_activated(self):
        """Handle voice assistant activation"""
        logger.info("Voice assistant activated callback")
        if not self.is_recording:
            threading.Thread(target=self._voice_assistant_session, daemon=True).start()

    def _voice_assistant_session(self):
        """Handle voice assistant recording session"""
        try:
            self.start_recording(auto_stop=True)

            # Wait for auto-stop or timeout
            timeout = self.config.get('voice_assistant.auto_stop_timeout', 3.0)
            start_time = time.time()

            while self.is_recording and (time.time() - start_time < timeout + 5):
                time.sleep(0.1)

            # Force stop if still recording
            if self.is_recording:
                self.stop_recording_and_transcribe()

        except Exception as e:
            logger.error(f"Voice assistant session error: {e}")

    def _on_auto_stop_triggered(self):
        """Handle auto-stop from audio recorder"""
        logger.info("Auto-stop triggered")
        if self.is_recording:
            self.stop_recording_and_transcribe()

    # Recording methods
    def start_recording(self, auto_stop=False):
        """Start recording"""
        try:
            success = self.audio_recorder.start_recording(auto_stop)
            if success:
                self.is_recording = True
                self.main_window.update_status("Recording...", "green")
                self.main_window.update_recording_indicator(True)

                if self.background_mode:
                    self.background_popup.start_recording_animation()

                logger.info(f"Recording started (auto_stop: {auto_stop})")
            else:
                self.main_window.update_status("Failed to start recording", "red")

        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self.main_window.update_status("Error starting recording", "red")

    def stop_recording_and_transcribe(self):
        """Stop recording and transcribe"""
        try:
            audio_data = self.audio_recorder.stop_recording()
            self.is_recording = False
            self.is_toggle_mode = False

            self.main_window.update_status("Processing...", "yellow")
            self.main_window.update_recording_indicator(False)

            if self.background_mode:
                self.background_popup.stop_recording_animation()

            if audio_data is not None and len(audio_data) > 1000:  # Minimum audio length
                threading.Thread(target=self._transcribe_and_paste, args=(audio_data,), daemon=True).start()
            else:
                self.main_window.update_status("No audio captured", "orange")
                if self.background_mode:
                    self.background_popup.update_status("No audio", recording=False)
                self._reset_status_delayed()

        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            self.main_window.update_status("Error processing audio", "red")
            self._reset_status_delayed()

    def toggle_recording(self):
        """Toggle recording state"""
        self.is_toggle_mode = True
        if self.is_recording:
            self.stop_recording_and_transcribe()
        else:
            self.start_recording()

    def _transcribe_and_paste(self, audio_data):
        """Transcribe audio and paste text"""
        try:
            text = self.transcriber.transcribe(audio_data)

            if text and len(text.strip()) > 0:
                self.main_window.add_transcription_to_log(text)
                self.text_injector.paste_text(text)
                self.main_window.update_status("Text pasted successfully", "green")
                if self.background_mode:
                    self.background_popup.update_status("Pasted!", recording=False)
            else:
                self.main_window.update_status("No speech detected", "orange")
                if self.background_mode:
                    self.background_popup.update_status("No speech", recording=False)

        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            self.main_window.update_status("Transcription error", "red")
            if self.background_mode:
                self.background_popup.update_status("Error", recording=False)

        self._reset_status_delayed()

    def _reset_status_delayed(self):
        """Reset status after delay"""
        def reset():
            time.sleep(2.0)
            self.main_window.update_status("Ready")
            if self.background_mode:
                self.background_popup.update_status("Ready", recording=False)

        threading.Thread(target=reset, daemon=True).start()

    # Window management
    def show_window(self, icon=None, item=None):
        """Show main window"""
        self.background_mode = False
        if self.background_popup.is_visible:
            self.background_popup.hide_popup()
        self.main_window.show()

    def hide_window(self):
        """Hide main window"""
        self.main_window.hide()

    def toggle_background_mode(self):
        """Toggle background mode"""
        if self.background_mode:
            self.disable_background_mode()
        else:
            self.enable_background_mode()

    def enable_background_mode(self):
        """Enable background mode"""
        self.background_mode = True
        self.hide_window()
        self.background_popup.show_popup()
        logger.info("Background mode enabled")

    def disable_background_mode(self):
        """Disable background mode"""
        self.background_mode = False
        self.background_popup.hide_popup()
        self.show_window()
        logger.info("Background mode disabled")

    def open_settings(self, icon=None, item=None):
        """Open settings window"""
        SettingsWindow(self.config, self)

    def on_closing(self):
        """Handle window close"""
        if self.config.get('ui.minimize_to_tray', True):
            self.enable_background_mode()
        else:
            self.quit_application()

    def quit_application(self, icon=None, item=None):
        """Quit application"""
        logger.info("Quitting application")
        self.cleanup()
        if self.tray_icon:
            self.tray_icon.stop()
        self.main_window.quit()

    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.is_recording:
                self.audio_recorder.stop_recording()
            self.audio_recorder.cleanup()
            self.hotkey_manager.stop_listening()
            self.hey_soffy.stop_listening()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def run(self):
        """Run the application"""
        try:
            logger.info("Starting VoiceType Pro Enhanced")
            self.main_window.run()
        except KeyboardInterrupt:
            logger.info("Application interrupted")
        except Exception as e:
            logger.error(f"Application error: {e}")
        finally:
            self.cleanup()
