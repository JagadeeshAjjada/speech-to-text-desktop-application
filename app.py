"""
VoiceType Pro - Professional Speech-to-Text Desktop Application
A robust, user-friendly desktop application that converts speech to text
and pastes it directly into the current cursor position in any application.

Features:
- Real-time speech-to-text using OpenAI Whisper (offline)
- Global hotkeys for activation
- Automatic text insertion at cursor position
- Configurable settings interface
- Multi-language support
- Press-and-hold or press-to-start/stop modes
- System tray integration
- Audio feedback and visual indicators

Requirements:
pip install tkinter customtkinter pynput pyaudio whisper torch sounddevice numpy threading queue
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import json
import os
import threading
import queue
import time
import pyaudio
import whisper
import numpy as np
import sounddevice as sd
from pynput import keyboard, mouse
from pynput.keyboard import Key, Listener as KeyboardListener
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import logging
import sys
from pathlib import Path
import winreg
import subprocess
import win32gui
import win32con

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration and settings"""

    def __init__(self):
        self.config_file = Path.home() / ".voicetype_pro" / "config.json"
        self.config_file.parent.mkdir(exist_ok=True)
        self.default_config = {
            "hotkeys": {
                "push_to_talk": ["ctrl", "alt"],
                "toggle_recording": ["ctrl", "shift"]
            },
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
                "device_index": None
            },
            "whisper": {
                "model_size": "base",
                "language": "auto",
                "task": "transcribe"
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
            }
        }
        self.load_config()

    def load_config(self):
        """Load configuration from file or create default"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self.config = {**self.default_config, **loaded_config}
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config = self.default_config.copy()

    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get(self, key_path, default=None):
        """Get config value using dot notation (e.g., 'audio.sample_rate')"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            value = value.get(key, default)
            if value is None:
                return default
        return value

    def set(self, key_path, value):
        """Set config value using dot notation"""
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            config = config.setdefault(key, {})
        config[keys[-1]] = value
        self.save_config()

class AudioRecorder:
    """Handles audio recording and processing"""

    def __init__(self, config_manager):
        self.config = config_manager
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.sample_rate = self.config.get('audio.sample_rate', 16000)
        self.channels = self.config.get('audio.channels', 1)
        self.chunk_size = self.config.get('audio.chunk_size', 1024)

        # Initialize PyAudio
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.audio_data = []

    def start_recording(self):
        """Start audio recording"""
        if self.is_recording:
            return

        try:
            self.is_recording = True
            self.audio_data = []

            # Configure audio stream
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
            logger.info("Recording started")

        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self.is_recording = False

    def stop_recording(self):
        """Stop audio recording and return audio data"""
        if not self.is_recording:
            return None

        try:
            self.is_recording = False

            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

            if self.audio_data:
                # Convert to numpy array
                audio_array = np.concatenate(self.audio_data)
                logger.info(f"Recording stopped, captured {len(audio_array)} samples")
                return audio_array

        except Exception as e:
            logger.error(f"Error stopping recording: {e}")

        return None

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio stream"""
        if self.is_recording:
            audio_chunk = np.frombuffer(in_data, dtype=np.float32)
            self.audio_data.append(audio_chunk)
        return (in_data, pyaudio.paContinue)

    def get_audio_devices(self):
        """Get list of available audio input devices"""
        devices = []
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': info['name'],
                    'channels': info['maxInputChannels']
                })
        return devices

    def cleanup(self):
        """Clean up audio resources"""
        if self.stream:
            self.stream.close()
        self.audio.terminate()

class WhisperTranscriber:
    """Handles speech-to-text transcription using Whisper"""

    def __init__(self, config_manager):
        self.config = config_manager
        self.model = None
        self.model_size = self.config.get('whisper.model_size', 'base')
        self.language = self.config.get('whisper.language', 'auto')
        self.task = self.config.get('whisper.task', 'transcribe')
        self.load_model()

    def load_model(self):
        """Load Whisper model"""
        try:
            logger.info(f"Loading Whisper model: {self.model_size}")
            self.model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}")
            raise

    def transcribe(self, audio_data):
        """Transcribe audio data to text"""
        if self.model is None:
            raise Exception("Whisper model not loaded")

        try:
            # Ensure audio is in the right format
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            # Normalize audio
            audio_data = audio_data / np.max(np.abs(audio_data))

            # Transcribe
            language = None if self.language == 'auto' else self.language
            result = self.model.transcribe(
                audio_data,
                language=language,
                task=self.task,
                fp16=False
            )

            text = result['text'].strip()

            # Post-process text
            text = self._post_process_text(text)

            logger.info(f"Transcription completed: {text[:50]}...")
            return text

        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return None

    def _post_process_text(self, text):
        """Post-process transcribed text"""
        if not text:
            return text

        # Remove filler words if enabled
        if self.config.get('behavior.remove_filler_words', True):
            filler_words = ['um', 'uh', 'er', 'ah', 'hmm']
            words = text.split()
            words = [word for word in words if word.lower() not in filler_words]
            text = ' '.join(words)

        # Capitalize sentences if enabled
        if self.config.get('behavior.capitalize_sentences', True):
            sentences = text.split('. ')
            sentences = [s.strip().capitalize() for s in sentences if s.strip()]
            text = '. '.join(sentences)

        # Add automatic punctuation if enabled
        if self.config.get('behavior.auto_punctuation', True):
            if text and not text.endswith(('.', '!', '?')):
                text += '.'

        return text

class HotkeyManager:
    """Manages global hotkeys and input handling"""

    def __init__(self, config_manager, callback_handler):
        self.config = config_manager
        self.callback_handler = callback_handler
        self.keyboard_listener = None
        self.current_keys = set()
        self.push_to_talk_active = False
        self.toggle_mode_active = False
        self.last_toggle_time = 0
        self.start_listening()

    def start_listening(self):
        """Start listening for global hotkeys"""
        try:
            self.keyboard_listener = KeyboardListener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
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

    def _on_key_press(self, key):
        """Handle key press events"""
        try:
            key_name = self._get_key_name(key)
            if key_name:
                self.current_keys.add(key_name)
                logger.debug(f"Key pressed: {key_name}, Current keys: {self.current_keys}")

                # Check for push-to-talk
                ptt_keys = set([k.lower().strip() for k in self.config.get('hotkeys.push_to_talk', [])])
                current_keys_normalized = set([k.lower().strip() for k in self.current_keys])

                if ptt_keys and ptt_keys.issubset(current_keys_normalized) and not self.push_to_talk_active:
                    logger.info("Push-to-talk activated")
                    self.push_to_talk_active = True
                    self.callback_handler.on_push_to_talk_start()

                # Check for toggle recording (prevent multiple triggers)
                toggle_keys = set([k.lower().strip() for k in self.config.get('hotkeys.toggle_recording', [])])
                current_time = time.time()

                if (toggle_keys and toggle_keys.issubset(current_keys_normalized) and
                    not self.toggle_mode_active and
                    current_time - self.last_toggle_time > 0.5):  # 500ms debounce

                    logger.info("Toggle recording activated")
                    self.toggle_mode_active = True
                    self.last_toggle_time = current_time
                    self.callback_handler.on_toggle_recording()

        except Exception as e:
            logger.error(f"Error handling key press: {e}")

    def _on_key_release(self, key):
        """Handle key release events"""
        try:
            key_name = self._get_key_name(key)
            if key_name:
                self.current_keys.discard(key_name)
                logger.debug(f"Key released: {key_name}, Current keys: {self.current_keys}")

                # Check if push-to-talk should be released
                ptt_keys = set([k.lower().strip() for k in self.config.get('hotkeys.push_to_talk', [])])
                current_keys_normalized = set([k.lower().strip() for k in self.current_keys])

                if self.push_to_talk_active and not ptt_keys.issubset(current_keys_normalized):
                    logger.info("Push-to-talk deactivated")
                    self.push_to_talk_active = False
                    self.callback_handler.on_push_to_talk_end()

                # Reset toggle processing when keys are released
                toggle_keys = set([k.lower().strip() for k in self.config.get('hotkeys.toggle_recording', [])])
                if not toggle_keys.issubset(current_keys_normalized):
                    self.toggle_mode_active = False

        except Exception as e:
            logger.error(f"Error handling key release: {e}")

    def _get_key_name(self, key):
        """Convert key object to string representation"""
        try:
            if hasattr(key, 'char') and key.char and key.char.isprintable():
                return key.char.lower()
            elif hasattr(key, 'name'):
                # Map special key names to standard format
                name_mapping = {
                    'ctrl_l': 'ctrl',
                    'ctrl_r': 'ctrl',
                    'alt_l': 'alt',
                    'alt_r': 'alt',
                    'shift_l': 'shift',
                    'shift_r': 'shift',
                    'cmd': 'cmd',
                    'cmd_l': 'cmd',
                    'cmd_r': 'cmd',
                    'win': 'win',
                    'win_l': 'win',
                    'win_r': 'win'
                }
                key_name = key.name.lower()
                return name_mapping.get(key_name, key_name)
            else:
                return str(key).lower().replace('key.', '').replace('<', '').replace('>', '')
        except Exception as e:
            logger.error(f"Error getting key name: {e}")
            return None


class TextInjector:
    """Handles text insertion at cursor position"""

    def __init__(self):
        self.controller = keyboard.Controller()

    def paste_text(self, text):
        """Paste text at current cursor position"""
        try:
            # Store current clipboard content
            import pyperclip
            original_clipboard = pyperclip.paste()

            # Copy new text to clipboard
            pyperclip.copy(text)

            # Small delay to ensure clipboard is updated
            time.sleep(0.1)

            # Paste using Ctrl+V
            with self.controller.pressed(Key.ctrl):
                self.controller.press('v')
                self.controller.release('v')

            # Restore original clipboard after a delay
            threading.Timer(0.01, lambda: pyperclip.copy(original_clipboard)).start()

            logger.info(f"Text pasted: {text[:50]}...")

        except Exception as e:
            logger.error(f"Error pasting text: {e}")
            # Fallback: type the text directly
            self._type_text(text)

    def _type_text(self, text):
        """Fallback method to type text directly"""
        try:
            self.controller.type(text)
        except Exception as e:
            logger.error(f"Error typing text: {e}")


class VoiceTypeProApp:
    """Main application class"""

    def __init__(self):
        self.config = ConfigManager()
        self.audio_recorder = AudioRecorder(self.config)
        self.transcriber = WhisperTranscriber(self.config)
        self.hotkey_manager = HotkeyManager(self.config, self)
        self.text_injector = TextInjector()
        self.background_popup = BackgroundPopup(self)
        self.auto_start_manager = AutoStartManager()
        self.background_mode = False

        self.is_recording = False
        self.is_toggle_mode = False
        self.root = None
        self.tray_icon = None

        # Initialize GUI
        self.setup_gui()

        # Initialize system tray
        self.setup_tray()

    def on_window_show(self, event=None):
        """Handle main window being shown"""
        if event and event.widget == self.root:
            # Hide popup when main window is shown
            if self.background_mode and self.background_popup.is_visible:
                self.background_popup.hide_popup()

    def on_window_hide(self, event=None):
        """Handle main window being hidden"""
        if event and event.widget == self.root:
            # Show popup when main window is hidden (only in background mode)
            if self.background_mode and not self.background_popup.is_visible:
                self.background_popup.show_popup()

    def setup_gui(self):
        """Setup the main GUI window"""
        ctk.set_appearance_mode(self.config.get('ui.theme', 'dark'))
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("VoiceType Pro")
        self.root.geometry("800x600")
        self.root.resizable(True, True)

        # Main container
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ctk.CTkLabel(
            main_frame,
            text="VoiceType Pro",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(20, 10))

        # Status indicator
        self.status_frame = ctk.CTkFrame(main_frame)
        self.status_frame.pack(fill="x", padx=20, pady=10)

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Ready",
            font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(side="left", padx=10, pady=10)

        self.recording_indicator = ctk.CTkLabel(
            self.status_frame,
            text="●",
            font=ctk.CTkFont(size=20),
            text_color="gray"
        )
        self.recording_indicator.pack(side="right", padx=10, pady=10)

        # Control buttons
        control_frame = ctk.CTkFrame(main_frame)
        control_frame.pack(fill="x", padx=20, pady=10)

        self.record_button = ctk.CTkButton(
            control_frame,
            text="Start Recording",
            command=self.toggle_recording,
            font=ctk.CTkFont(size=14)
        )
        self.record_button.pack(side="left", padx=10, pady=10)

        settings_button = ctk.CTkButton(
            control_frame,
            text="Settings",
            command=self.open_settings,
            font=ctk.CTkFont(size=14)
        )
        settings_button.pack(side="right", padx=10, pady=10)

        # Hotkey display
        hotkey_frame = ctk.CTkFrame(main_frame)
        hotkey_frame.pack(fill="x", padx=20, pady=10)

        ptt_keys = " + ".join(self.config.get('hotkeys.push_to_talk', []))
        toggle_keys = " + ".join(self.config.get('hotkeys.toggle_recording', []))

        hotkey_info = ctk.CTkLabel(
            hotkey_frame,
            text=f"Push-to-Talk: {ptt_keys}\nToggle Recording: {toggle_keys}",
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        hotkey_info.pack(padx=20, pady=15)

        # Recent transcriptions
        self.setup_transcription_log(main_frame)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Handle window events for popup management
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<Map>", self.on_window_show)      # Window shown
        self.root.bind("<Unmap>", self.on_window_hide)    # Window hidden

    def setup_transcription_log(self, parent):
        """Setup the transcription log display"""
        log_frame = ctk.CTkFrame(parent)
        log_frame.pack(fill="both", expand=True, padx=20, pady=10)

        log_label = ctk.CTkLabel(
            log_frame,
            text="Recent Transcriptions",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        log_label.pack(pady=(10, 5))

        self.transcription_log = ctk.CTkTextbox(
            log_frame,
            height=200,
            font=ctk.CTkFont(size=12)
        )
        self.transcription_log.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    def setup_tray(self):
        """Setup system tray icon"""
        try:
            # Create icon image
            image = Image.new('RGB', (64, 64), color='blue')
            draw = ImageDraw.Draw(image)
            draw.ellipse([16, 16, 48, 48], fill='white')

            # Create menu with background mode option
            menu = pystray.Menu(
                item('Show', self.show_window),
                item('Background Mode', self.toggle_background_mode),
                item('Settings', self.open_settings),
                pystray.Menu.SEPARATOR,
                item('Exit', self.quit_application)
            )

            self.tray_icon = pystray.Icon(
                "VoiceType Pro",
                image,
                menu=menu
            )

            # Run tray in separate thread
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

        except Exception as e:
            logger.error(f"Error setting up system tray: {e}")

    def show_window(self, icon=None, item=None):
        """Show the main window"""
        if self.root:
            self.background_mode = False  # Disable background mode when showing main window
            if self.background_popup.is_visible:
                self.background_popup.hide_popup()
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

    def hide_window(self):
        """Hide the main window to tray"""
        if self.root:
            self.root.withdraw()

    def on_closing(self):
        """Handle window close event"""
        if self.config.get('ui.minimize_to_tray', True):
            self.enable_background_mode()
        else:
            self.quit_application()

    def quit_application(self, icon=None, item=None):
        """Quit the application"""
        self.cleanup()
        if self.tray_icon:
            self.tray_icon.stop()
        if self.root:
            self.root.quit()
        sys.exit()

    def cleanup(self):
        """Clean up resources"""
        if self.is_recording:
            self.audio_recorder.stop_recording()
        self.audio_recorder.cleanup()
        self.hotkey_manager.stop_listening()

    def update_status(self, message, color="white"):
        """Update status display"""
        if self.status_label:
            self.status_label.configure(text=message, text_color=color)

    def update_recording_indicator(self, recording):
        """Update recording indicator"""
        if self.recording_indicator:
            color = "red" if recording else "gray"
            self.recording_indicator.configure(text_color=color)

    def add_transcription_to_log(self, text):
        """Add transcription to the log display"""
        if self.transcription_log:
            timestamp = time.strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {text}\n"
            self.transcription_log.insert("end", log_entry)
            self.transcription_log.see("end")

    # Hotkey callback methods
    def on_push_to_talk_start(self):
        """Handle push-to-talk start"""
        if not self.is_recording:
            self.start_recording()

    def on_push_to_talk_end(self):
        """Handle push-to-talk end"""
        logger.info(f"My understanding: {self.is_recording}, {self.is_toggle_mode}")
        if self.is_recording and not self.is_toggle_mode:
            self.stop_recording_and_transcribe()

    def on_toggle_recording(self):
        """Handle toggle recording hotkey"""
        self.toggle_recording()

    def toggle_recording(self):
        """Toggle recording state"""
        self.is_toggle_mode = True
        if self.is_recording:
            self.stop_recording_and_transcribe()
        else:
            self.start_recording()

    def start_recording(self):
        """Start recording audio"""
        try:
            self.audio_recorder.start_recording()
            self.is_recording = True

            self.update_status("Recording...", "green")
            self.update_recording_indicator(True)

            # Start popup animation if in background mode
            if self.background_mode:
                self.background_popup.start_recording_animation()

            if self.record_button:
                self.record_button.configure(text="Stop Recording")

        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self.update_status("Error starting recording", "red")

    def stop_recording_and_transcribe(self):
        """Stop recording and transcribe audio"""
        try:
            audio_data = self.audio_recorder.stop_recording()
            self.is_recording = False
            self.is_toggle_mode = False

            self.update_status("Processing...", "yellow")
            self.update_recording_indicator(False)

            # Stop popup animation if in background mode
            if self.background_mode:
                self.background_popup.stop_recording_animation()

            if self.record_button:
                self.record_button.configure(text="Start Recording")

            if audio_data is not None and len(audio_data) > 0:
                # Transcribe in separate thread
                threading.Thread(
                    target=self.transcribe_and_paste,
                    args=(audio_data,),
                    daemon=True
                ).start()
            else:
                self.update_status("No audio captured", "orange")
                # Update popup status too
                if self.background_mode:
                    self.background_popup.update_status("No audio", recording=False)

        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            self.update_status("Error processing audio", "red")
            if self.background_mode:
                self.background_popup.update_status("Error", recording=False)

    def transcribe_and_paste(self, audio_data):
        """Transcribe audio and paste text"""
        try:
            # Transcribe
            text = self.transcriber.transcribe(audio_data)

            if text:
                # Add to log
                self.add_transcription_to_log(text)

                # Paste text
                self.text_injector.paste_text(text)

                self.update_status("Text pasted successfully", "green")
                if self.background_mode:
                    self.background_popup.update_status("Pasted!", recording=False)
            else:
                self.update_status("No speech detected", "orange")
                if self.background_mode:
                    self.background_popup.update_status("No speech", recording=False)

        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            self.update_status("Transcription error", "red")
            if self.background_mode:
                self.background_popup.update_status("Error", recording=False)

        # Reset status after delay
        threading.Timer(0.10, lambda: self.update_status("Ready")).start()
        if self.background_mode:
            threading.Timer(0.10, lambda: self.background_popup.update_status("Ready", recording=False)).start()

    def open_settings(self, icon=None, item=None):
        """Open settings window"""
        SettingsWindow(self.config, self)

    def run(self):
        """Run the application"""
        try:
            logger.info("Starting VoiceType Pro")
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
        except Exception as e:
            logger.error(f"Application error: {e}")
        finally:
            self.cleanup()

    def toggle_background_mode(self):
        """Toggle background mode"""
        if self.background_mode:
            self.disable_background_mode()
        else:
            self.enable_background_mode()

    def enable_background_mode(self):
        """Enable background mode with popup"""
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


class SettingsWindow:
    """Settings configuration window"""

    def __init__(self, config_manager, parent_app):
        self.config = config_manager
        self.parent_app = parent_app
        self.window = None
        self.setup_window()

    def setup_window(self):
        """Setup settings window"""
        self.window = ctk.CTkToplevel()
        self.window.title("VoiceType Pro - Settings")
        self.window.geometry("600x500")
        self.window.resizable(True, True)

        # Make window modal
        self.window.transient(self.parent_app.root)
        self.window.grab_set()

        # Main container with tabs
        self.notebook = ctk.CTkTabview(self.window)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=20)

        # Create tabs
        self.setup_hotkeys_tab()
        self.setup_audio_tab()
        self.setup_whisper_tab()
        self.setup_behavior_tab()
        self.setup_ui_tab()

        # Buttons
        button_frame = ctk.CTkFrame(self.window)
        button_frame.pack(fill="x", padx=20, pady=(0, 20))

        save_button = ctk.CTkButton(
            button_frame,
            text="Save",
            command=self.save_settings
        )
        save_button.pack(side="right", padx=(10, 0), pady=10)

        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self.close_window
        )
        cancel_button.pack(side="right", pady=10)

    def setup_hotkeys_tab(self):
        """Setup hotkeys configuration tab"""
        tab = self.notebook.add("Hotkeys")

        # Push-to-talk hotkey
        ptt_frame = ctk.CTkFrame(tab)
        ptt_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(ptt_frame, text="Push-to-Talk Hotkey:").pack(anchor="w", padx=10, pady=5)
        self.ptt_entry = ctk.CTkEntry(ptt_frame, placeholder_text="Click to set hotkey")
        self.ptt_entry.pack(fill="x", padx=10, pady=5)

        # Toggle recording hotkey
        toggle_frame = ctk.CTkFrame(tab)
        toggle_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(toggle_frame, text="Toggle Recording Hotkey:").pack(anchor="w", padx=10, pady=5)
        self.toggle_entry = ctk.CTkEntry(toggle_frame, placeholder_text="Click to set hotkey")
        self.toggle_entry.pack(fill="x", padx=10, pady=5)

        # Load current values
        ptt_keys = " + ".join(self.config.get('hotkeys.push_to_talk', []))
        toggle_keys = " + ".join(self.config.get('hotkeys.toggle_recording', []))

        self.ptt_entry.insert(0, ptt_keys)
        self.toggle_entry.insert(0, toggle_keys)

    def setup_audio_tab(self):
        """Setup audio configuration tab"""
        tab = self.notebook.add("Audio")

        # Audio device selection
        device_frame = ctk.CTkFrame(tab)
        device_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(device_frame, text="Audio Input Device:").pack(anchor="w", padx=10, pady=5)

        # Get available audio devices
        devices = self.parent_app.audio_recorder.get_audio_devices()
        device_names = [f"{d['name']} ({d['channels']} ch)" for d in devices]

        self.device_combo = ctk.CTkComboBox(device_frame, values=device_names)
        self.device_combo.pack(fill="x", padx=10, pady=5)

        # Sample rate
        rate_frame = ctk.CTkFrame(tab)
        rate_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(rate_frame, text="Sample Rate:").pack(anchor="w", padx=10, pady=5)
        self.sample_rate_combo = ctk.CTkComboBox(
            rate_frame,
            values=["8000", "16000", "22050", "44100", "48000"]
        )
        self.sample_rate_combo.pack(fill="x", padx=10, pady=5)
        self.sample_rate_combo.set(str(self.config.get('audio.sample_rate', 16000)))

        # Audio quality settings
        quality_frame = ctk.CTkFrame(tab)
        quality_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(quality_frame, text="Audio Quality Settings:").pack(anchor="w", padx=10, pady=5)

        self.noise_reduction = ctk.CTkCheckBox(quality_frame, text="Enable Noise Reduction")
        self.noise_reduction.pack(anchor="w", padx=10, pady=2)

        self.auto_gain = ctk.CTkCheckBox(quality_frame, text="Automatic Gain Control")
        self.auto_gain.pack(anchor="w", padx=10, pady=2)

    def setup_whisper_tab(self):
        """Setup Whisper model configuration tab"""
        tab = self.notebook.add("Transcription")

        # Model size selection
        model_frame = ctk.CTkFrame(tab)
        model_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(model_frame, text="Whisper Model Size:").pack(anchor="w", padx=10, pady=5)

        model_info = {
            "tiny": "Tiny (39 MB) - Fastest, least accurate",
            "base": "Base (74 MB) - Good balance",
            "small": "Small (244 MB) - Better accuracy",
            "medium": "Medium (769 MB) - High accuracy",
            "large": "Large (1550 MB) - Best accuracy"
        }

        self.model_combo = ctk.CTkComboBox(
            model_frame,
            values=list(model_info.values())
        )
        self.model_combo.pack(fill="x", padx=10, pady=5)

        current_model = self.config.get('whisper.model_size', 'base')
        if current_model in model_info:
            self.model_combo.set(model_info[current_model])

        # Language selection
        lang_frame = ctk.CTkFrame(tab)
        lang_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(lang_frame, text="Language:").pack(anchor="w", padx=10, pady=5)

        languages = [
            "auto", "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko",
            "zh", "ar", "hi", "tr", "pl", "nl", "sv", "da", "no", "fi"
        ]

        self.language_combo = ctk.CTkComboBox(lang_frame, values=languages)
        self.language_combo.pack(fill="x", padx=10, pady=5)
        self.language_combo.set(self.config.get('whisper.language', 'auto'))

        # Task selection
        task_frame = ctk.CTkFrame(tab)
        task_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(task_frame, text="Task:").pack(anchor="w", padx=10, pady=5)
        self.task_combo = ctk.CTkComboBox(task_frame, values=["transcribe", "translate"])
        self.task_combo.pack(fill="x", padx=10, pady=5)
        self.task_combo.set(self.config.get('whisper.task', 'transcribe'))

    def setup_behavior_tab(self):
        """Setup behavior configuration tab"""
        tab = self.notebook.add("Behavior")

        # Text processing options
        processing_frame = ctk.CTkFrame(tab)
        processing_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(processing_frame, text="Text Processing:").pack(anchor="w", padx=10, pady=5)

        self.auto_punctuation = ctk.CTkCheckBox(
            processing_frame,
            text="Add automatic punctuation"
        )
        self.auto_punctuation.pack(anchor="w", padx=10, pady=2)
        if self.config.get('behavior.auto_punctuation', True):
            self.auto_punctuation.select()

        self.capitalize_sentences = ctk.CTkCheckBox(
            processing_frame,
            text="Capitalize sentences"
        )
        self.capitalize_sentences.pack(anchor="w", padx=10, pady=2)
        if self.config.get('behavior.capitalize_sentences', True):
            self.capitalize_sentences.select()

        self.remove_filler_words = ctk.CTkCheckBox(
            processing_frame,
            text="Remove filler words (um, uh, etc.)"
        )
        self.remove_filler_words.pack(anchor="w", padx=10, pady=2)
        if self.config.get('behavior.remove_filler_words', True):
            self.remove_filler_words.select()

        # Confidence threshold
        confidence_frame = ctk.CTkFrame(tab)
        confidence_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(confidence_frame, text="Confidence Threshold:").pack(anchor="w", padx=10, pady=5)

        self.confidence_slider = ctk.CTkSlider(
            confidence_frame,
            from_=0.1,
            to=1.0,
            number_of_steps=9
        )
        self.confidence_slider.pack(fill="x", padx=10, pady=5)
        self.confidence_slider.set(self.config.get('behavior.confidence_threshold', 0.7))

        self.confidence_label = ctk.CTkLabel(confidence_frame, text="0.7")
        self.confidence_label.pack(padx=10, pady=2)

        # Update label when slider changes
        self.confidence_slider.configure(command=self.update_confidence_label)

    def setup_ui_tab(self):
        """Setup UI configuration tab"""
        tab = self.notebook.add("Interface")

        # Theme selection
        theme_frame = ctk.CTkFrame(tab)
        theme_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(theme_frame, text="Theme:").pack(anchor="w", padx=10, pady=5)
        self.theme_combo = ctk.CTkComboBox(theme_frame, values=["dark", "light", "system"])
        self.theme_combo.pack(fill="x", padx=10, pady=5)
        self.theme_combo.set(self.config.get('ui.theme', 'dark'))

        # System integration options
        integration_frame = ctk.CTkFrame(tab)
        integration_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(integration_frame, text="System Integration:").pack(anchor="w", padx=10, pady=5)

        self.minimize_to_tray = ctk.CTkCheckBox(
            integration_frame,
            text="Minimize to system tray"
        )
        self.minimize_to_tray.pack(anchor="w", padx=10, pady=2)
        if self.config.get('ui.minimize_to_tray', True):
            self.minimize_to_tray.select()

        self.show_notifications = ctk.CTkCheckBox(
            integration_frame,
            text="Show desktop notifications"
        )
        self.show_notifications.pack(anchor="w", padx=10, pady=2)
        if self.config.get('ui.show_notifications', True):
            self.show_notifications.select()

        # AUTO-START TOGGLE SWITCH - This is the main addition you requested
        self.auto_start = ctk.CTkSwitch(
            integration_frame,
            text="Auto-start when Windows boots",
            command=self.on_auto_start_toggle
        )
        self.auto_start.pack(anchor="w", padx=10, pady=5)

        # Set initial state based on current auto-start status
        if self.parent_app.auto_start_manager.is_auto_start_enabled():
            self.auto_start.select()

    def update_confidence_label(self, value):
        """Update confidence threshold label"""
        self.confidence_label.configure(text=f"{value:.1f}")

    def save_settings(self):
        """Save all settings"""
        try:
            # Hotkeys
            ptt_keys = self.ptt_entry.get().split(" + ")
            toggle_keys = self.toggle_entry.get().split(" + ")

            self.config.set('hotkeys.push_to_talk', [k.strip().lower() for k in ptt_keys if k.strip()])
            self.config.set('hotkeys.toggle_recording', [k.strip().lower() for k in toggle_keys if k.strip()])

            # Audio
            self.config.set('audio.sample_rate', int(self.sample_rate_combo.get()))

            # Whisper
            model_mapping = {
                "Tiny (39 MB) - Fastest, least accurate": "tiny",
                "Base (74 MB) - Good balance": "base",
                "Small (244 MB) - Better accuracy": "small",
                "Medium (769 MB) - High accuracy": "medium",
                "Large (1550 MB) - Best accuracy": "large"
            }

            selected_model = self.model_combo.get()
            if selected_model in model_mapping:
                self.config.set('whisper.model_size', model_mapping[selected_model])

            self.config.set('whisper.language', self.language_combo.get())
            self.config.set('whisper.task', self.task_combo.get())

            # Behavior
            self.config.set('behavior.auto_punctuation', bool(self.auto_punctuation.get()))
            self.config.set('behavior.capitalize_sentences', bool(self.capitalize_sentences.get()))
            self.config.set('behavior.remove_filler_words', bool(self.remove_filler_words.get()))
            self.config.set('behavior.confidence_threshold', self.confidence_slider.get())

            # UI
            self.config.set('ui.theme', self.theme_combo.get())
            self.config.set('ui.minimize_to_tray', bool(self.minimize_to_tray.get()))
            self.config.set('ui.show_notifications', bool(self.show_notifications.get()))
            # self.config.set('ui.auto_start', bool(self.auto_start.get()))

            # Apply theme change
            if self.theme_combo.get() != self.config.get('ui.theme'):
                ctk.set_appearance_mode(self.theme_combo.get())

            messagebox.showinfo("Settings", "Settings saved successfully!")
            self.close_window()

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def on_auto_start_toggle(self):
        """Handle auto-start toggle switch"""
        try:
            if self.auto_start.get():
                success = self.parent_app.auto_start_manager.enable_auto_start()
                if not success:
                    self.auto_start.deselect()
                    messagebox.showerror("Error", "Failed to enable auto-start")
            else:
                success = self.parent_app.auto_start_manager.disable_auto_start()
                if not success:
                    self.auto_start.select()
                    messagebox.showerror("Error", "Failed to disable auto-start")

            # Update config
            self.config.set('ui.auto_start', bool(self.auto_start.get()))

        except Exception as e:
            logger.error(f"Error toggling auto-start: {e}")
            messagebox.showerror("Error", f"Auto-start toggle failed: {e}")

    def close_window(self):
        """Close settings window"""
        self.window.destroy()


class BackgroundPopup:
    """Sleek background popup with recording animation and controls"""

    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.popup = None
        self.is_visible = False
        self.animation_active = False
        self.animation_frame = 0
        self.drag_data = {"x": 0, "y": 0}

    def create_popup(self):
        """Create the enhanced background popup with controls"""
        if self.popup is None:
            self.popup = ctk.CTkToplevel()
            self.popup.title("")
            self.popup.geometry("200x60")  # Increased size for buttons
            self.popup.resizable(False, False)

            # Remove window decorations and make it stay on top
            self.popup.overrideredirect(True)
            self.popup.attributes('-topmost', True)
            self.popup.attributes('-alpha', 0.95)

            # Position at top-right corner
            self.popup.geometry("+{}+20".format(self.popup.winfo_screenwidth() - 220))

            # Create main frame with rounded appearance
            self.main_frame = ctk.CTkFrame(
                self.popup,
                corner_radius=15,
                fg_color=("#2b2b2b", "#1a1a1a"),
                border_width=1,
                border_color=("#404040", "#303030")
            )
            self.main_frame.pack(fill="both", expand=True, padx=2, pady=2)

            # Enable dragging
            self.main_frame.bind("<Button-1>", self.start_drag)
            self.main_frame.bind("<B1-Motion>", self.on_drag)

            # Top row with mic icon and status
            self.top_frame = ctk.CTkFrame(
                self.main_frame,
                fg_color="transparent",
                height=30
            )
            self.top_frame.pack(fill="x", padx=5, pady=(5, 2))
            self.top_frame.pack_propagate(False)

            # Make top frame draggable too
            self.top_frame.bind("<Button-1>", self.start_drag)
            self.top_frame.bind("<B1-Motion>", self.on_drag)

            self.mic_label = ctk.CTkLabel(
                self.top_frame,
                text="🎤",
                font=ctk.CTkFont(size=16),
                text_color="gray"
            )
            self.mic_label.pack(side="left", pady=2)
            self.mic_label.bind("<Button-1>", self.start_drag)
            self.mic_label.bind("<B1-Motion>", self.on_drag)

            self.status_label = ctk.CTkLabel(
                self.top_frame,
                text="Ready",
                font=ctk.CTkFont(size=10),
                text_color="gray"
            )
            self.status_label.pack(side="left", padx=(5, 0), pady=2)
            self.status_label.bind("<Button-1>", self.start_drag)
            self.status_label.bind("<B1-Motion>", self.on_drag)

            self.status_dot = ctk.CTkLabel(
                self.top_frame,
                text="●",
                font=ctk.CTkFont(size=12),
                text_color="gray"
            )
            self.status_dot.pack(side="right", padx=2, pady=2)
            self.status_dot.bind("<Button-1>", self.start_drag)
            self.status_dot.bind("<B1-Motion>", self.on_drag)

            # Bottom row with buttons
            self.button_frame = ctk.CTkFrame(
                self.main_frame,
                fg_color="transparent",
                height=25
            )
            self.button_frame.pack(fill="x", padx=5, pady=(2, 5))
            self.button_frame.pack_propagate(False)

            # Stop Recording button
            self.stop_button = ctk.CTkButton(
                self.button_frame,
                text="Stop",
                width=50,
                height=20,
                font=ctk.CTkFont(size=10),
                fg_color=("#cc4444", "#aa3333"),
                hover_color=("#dd5555", "#bb4444"),
                command=self.stop_recording,
                state="disabled"
            )
            self.stop_button.pack(side="left", padx=(0, 5))

            # Settings button
            self.settings_button = ctk.CTkButton(
                self.button_frame,
                text="Settings",
                width=60,
                height=20,
                font=ctk.CTkFont(size=10),
                fg_color=("#444444", "#333333"),
                hover_color=("#555555", "#444444"),
                command=self.open_settings
            )
            self.settings_button.pack(side="left", padx=(0, 5))

            # Close button
            # self.close_button = ctk.CTkButton(
            #     self.button_frame,
            #     text="×",
            #     width=20,
            #     height=20,
            #     font=ctk.CTkFont(size=12, weight="bold"),
            #     fg_color=("#666666", "#555555"),
            #     hover_color=("#777777", "#666666"),
            #     command=self.hide_popup
            # )
            # self.close_button.pack(side="right")

            # Hide initially
            self.popup.withdraw()

    def start_drag(self, event):
        """Start dragging the popup"""
        self.drag_data["x"] = event.x_root - self.popup.winfo_x()
        self.drag_data["y"] = event.y_root - self.popup.winfo_y()

    def on_drag(self, event):
        """Handle popup dragging"""
        new_x = event.x_root - self.drag_data["x"]
        new_y = event.y_root - self.drag_data["y"]

        # Keep popup within screen bounds
        screen_width = self.popup.winfo_screenwidth()
        screen_height = self.popup.winfo_screenheight()
        popup_width = self.popup.winfo_width()
        popup_height = self.popup.winfo_height()

        new_x = max(0, min(new_x, screen_width - popup_width))
        new_y = max(0, min(new_y, screen_height - popup_height))

        self.popup.geometry(f"+{new_x}+{new_y}")

    def stop_recording(self):
        """Stop recording through parent app"""
        if self.parent_app.is_recording:
            self.parent_app.stop_recording_and_transcribe()

    def open_settings(self):
        """Open settings and show main window"""
        self.parent_app.show_window()

    def show_popup(self):
        """Show the popup"""
        if self.popup is None:
            self.create_popup()

        self.popup.deiconify()
        self.popup.lift()
        self.is_visible = True

    def hide_popup(self):
        """Hide the popup"""
        if self.popup:
            self.popup.withdraw()
        self.is_visible = False
        self.stop_recording_animation()

    def update_status(self, message, recording=False):
        """Update popup status"""
        if self.status_label:
            self.status_label.configure(text=message)

        if self.stop_button:
            if recording:
                self.stop_button.configure(state="normal")
            else:
                self.stop_button.configure(state="disabled")

    def start_recording_animation(self):
        """Start the recording animation"""
        self.animation_active = True
        self.animation_frame = 0
        self.update_status("Recording...", recording=True)
        self.animate_recording()

    def stop_recording_animation(self):
        """Stop the recording animation"""
        self.animation_active = False
        self.update_status("Ready", recording=False)
        if self.mic_label:
            self.mic_label.configure(text_color="gray")
        if self.status_dot:
            self.status_dot.configure(text_color="gray")

    def animate_recording(self):
        """Animate the recording indicator"""
        if not self.animation_active or not self.popup:
            return

        # Pulsing red animation
        colors = ["#ff4444", "#ff6666", "#ff8888", "#ffaaaa", "#ff8888", "#ff6666"]
        color = colors[self.animation_frame % len(colors)]

        if self.mic_label:
            self.mic_label.configure(text_color=color)
        if self.status_dot:
            self.status_dot.configure(text_color=color)

        self.animation_frame += 1

        # Schedule next frame
        if self.popup:
            self.popup.after(200, self.animate_recording)


# This class for auto-start management
class AutoStartManager:
    """Manages Windows auto-start functionality"""

    def __init__(self, app_name="VoiceType Pro"):
        self.app_name = app_name
        self.registry_key = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def is_auto_start_enabled(self):
        """Check if auto-start is currently enabled"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_key) as key:
                try:
                    winreg.QueryValueEx(key, self.app_name)
                    return True
                except FileNotFoundError:
                    return False
        except Exception as e:
            logger.error(f"Error checking auto-start status: {e}")
            return False

    def enable_auto_start(self):
        """Enable auto-start on Windows boot"""
        try:
            exe_path = sys.executable
            if exe_path.endswith("python.exe"):
                # If running from Python, use the script path
                script_path = os.path.abspath(__file__)
                exe_path = f'"{exe_path}" "{script_path}"'
            else:
                exe_path = f'"{exe_path}"'

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, exe_path)

            logger.info("Auto-start enabled successfully")
            return True

        except Exception as e:
            logger.error(f"Error enabling auto-start: {e}")
            return False

    def disable_auto_start(self):
        """Disable auto-start on Windows boot"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_key, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, self.app_name)
                    logger.info("Auto-start disabled successfully")
                    return True
                except FileNotFoundError:
                    # Already disabled
                    return True

        except Exception as e:
            logger.error(f"Error disabling auto-start: {e}")
            return False


def main():
    """Main entry point"""
    try:
        # Check required dependencies
        required_packages = [
            'whisper', 'torch', 'pyaudio', 'sounddevice',
            'pynput', 'customtkinter', 'pystray', 'pyperclip'
        ]

        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)

        if missing_packages:
            print("Missing required packages:")
            for package in missing_packages:
                print(f"  - {package}")
            print("\nInstall missing packages with:")
            print(f"pip install {' '.join(missing_packages)}")
            return

        # Create and run application
        app = VoiceTypeProApp()
        app.run()

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
