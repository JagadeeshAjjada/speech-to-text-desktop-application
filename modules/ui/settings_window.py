# =============================================================================
# UI MODULE - Settings Window
# File: modules/ui/settings_window.py
# =============================================================================

import customtkinter as ctk
from tkinter import messagebox
import threading
import time
from pynput import keyboard
from pynput.keyboard import Key, Listener as KeyboardListener
import logging

logger = logging.getLogger(__name__)

class SettingsWindow:
    """Enhanced settings window with modular tabs"""

    def __init__(self, config, app):
        self.config = config
        self.app = app
        self.window = None
        self.setup_window()

    def setup_window(self):
        """Setup main settings window"""
        self.window = ctk.CTkToplevel()
        self.window.title("VoiceType Pro - Settings")
        self.window.geometry("700x600")
        self.window.resizable(True, True)

        self.window.transient(self.app.main_window.root)
        self.window.grab_set()

        # Main tabview
        self.notebook = ctk.CTkTabview(self.window)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=20)

        # Initialize tabs
        self.hotkeys_tab = HotkeysTab(self.notebook.add("Hotkeys"), self.config)
        self.audio_tab = AudioTab(self.notebook.add("Audio"), self.config, self.app)
        self.whisper_tab = WhisperTab(self.notebook.add("Transcription"), self.config)
        self.voice_assistant_tab = VoiceAssistantTab(self.notebook.add("Voice Assistant"), self.config)
        self.behavior_tab = BehaviorTab(self.notebook.add("Behavior"), self.config)
        self.ui_tab = UITab(self.notebook.add("Interface"), self.config, self.app)
        self.sounds_tab = SoundsTab(self.notebook.add("Sounds"), self.config)

        # Buttons
        self.setup_buttons()

    def setup_buttons(self):
        """Setup save/cancel buttons"""
        button_frame = ctk.CTkFrame(self.window)
        button_frame.pack(fill="x", padx=20, pady=(0, 20))

        save_button = ctk.CTkButton(button_frame, text="Save", command=self.save_settings)
        save_button.pack(side="right", padx=(10, 0), pady=10)

        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.close_window)
        cancel_button.pack(side="right", pady=10)

    def save_settings(self):
        """Save all settings"""
        try:
            # Save each tab's settings
            self.hotkeys_tab.save_settings()
            self.audio_tab.save_settings()
            self.whisper_tab.save_settings()
            self.voice_assistant_tab.save_settings()
            self.behavior_tab.save_settings()
            self.ui_tab.save_settings()
            self.sounds_tab.save_settings()

            # Update app components
            self.app.main_window.update_hotkey_display()
            self.app.hotkey_manager.update_hotkeys()

            # Restart voice assistant if settings changed
            va_enabled = self.config.get('voice_assistant.enabled', True)
            if va_enabled:
                self.app.hey_soffy.stop_listening()
                time.sleep(0.1)
                self.app.hey_soffy.start_listening()
            else:
                self.app.hey_soffy.stop_listening()

            messagebox.showinfo("Settings", "Settings saved successfully!")
            self.close_window()

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def close_window(self):
        """Close settings window"""
        if hasattr(self.hotkeys_tab, 'cleanup'):
            self.hotkeys_tab.cleanup()
        self.window.destroy()

class HotkeysTab:
    """Hotkeys configuration tab with key recording"""

    def __init__(self, tab, config):
        self.tab = tab
        self.config = config
        self.recording_hotkey = None
        self.current_keys = set()
        self.key_listener = None
        self.setup_tab()

    def setup_tab(self):
        """Setup hotkeys tab"""
        # Instructions
        instructions = ctk.CTkLabel(
            self.tab,
            text="Click 'Record' and press your desired key combination",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        instructions.pack(pady=10)

        # Push-to-talk
        ptt_frame = ctk.CTkFrame(self.tab)
        ptt_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(ptt_frame, text="Push-to-Talk Hotkey:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        ptt_container = ctk.CTkFrame(ptt_frame)
        ptt_container.pack(fill="x", padx=10, pady=5)

        self.ptt_entry = ctk.CTkEntry(ptt_container, placeholder_text="No hotkey set")
        self.ptt_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.ptt_record_btn = ctk.CTkButton(
            ptt_container,
            text="Record",
            width=80,
            command=lambda: self.start_recording_hotkey('ptt')
        )
        self.ptt_record_btn.pack(side="right")

        # Toggle recording
        toggle_frame = ctk.CTkFrame(self.tab)
        toggle_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(toggle_frame, text="Toggle Recording Hotkey:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        toggle_container = ctk.CTkFrame(toggle_frame)
        toggle_container.pack(fill="x", padx=10, pady=5)

        self.toggle_entry = ctk.CTkEntry(toggle_container, placeholder_text="No hotkey set")
        self.toggle_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.toggle_record_btn = ctk.CTkButton(
            toggle_container,
            text="Record",
            width=80,
            command=lambda: self.start_recording_hotkey('toggle')
        )
        self.toggle_record_btn.pack(side="right")

        # Load current values
        self.load_current_hotkeys()

    def load_current_hotkeys(self):
        """Load current hotkey values"""
        ptt_keys = " + ".join(self.config.get('hotkeys.push_to_talk', [])).title()
        toggle_keys = " + ".join(self.config.get('hotkeys.toggle_recording', [])).title()

        self.ptt_entry.delete(0, 'end')
        self.ptt_entry.insert(0, ptt_keys)

        self.toggle_entry.delete(0, 'end')
        self.toggle_entry.insert(0, toggle_keys)

    def start_recording_hotkey(self, hotkey_type):
        """Start recording hotkey"""
        self.recording_hotkey = hotkey_type
        self.current_keys.clear()

        # Update UI
        if hotkey_type == 'ptt':
            self.ptt_record_btn.configure(text="Press keys...")
            self.ptt_entry.delete(0, 'end')
            self.ptt_entry.insert(0, "Press your key combination...")
        else:
            self.toggle_record_btn.configure(text="Press keys...")
            self.toggle_entry.delete(0, 'end')
            self.toggle_entry.insert(0, "Press your key combination...")

        # Start listener
        self.key_listener = KeyboardListener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.key_listener.start()

        # Auto-stop after 5 seconds
        threading.Timer(5.0, self.stop_recording_hotkey).start()

    def stop_recording_hotkey(self):
        """Stop recording hotkey"""
        if self.key_listener:
            self.key_listener.stop()
            self.key_listener = None

        if self.recording_hotkey:
            keys_text = " + ".join(sorted(self.current_keys)).title()

            if self.recording_hotkey == 'ptt':
                self.ptt_entry.delete(0, 'end')
                self.ptt_entry.insert(0, keys_text or "No keys recorded")
                self.ptt_record_btn.configure(text="Record")
            else:
                self.toggle_entry.delete(0, 'end')
                self.toggle_entry.insert(0, keys_text or "No keys recorded")
                self.toggle_record_btn.configure(text="Record")

        self.recording_hotkey = None
        self.current_keys.clear()

    def _on_key_press(self, key):
        """Handle key press during recording"""
        try:
            key_name = self._get_key_name(key)
            if key_name:
                self.current_keys.add(key_name)

                # Update display in real-time
                keys_text = " + ".join(sorted(self.current_keys)).title()
                if self.recording_hotkey == 'ptt':
                    self.ptt_entry.delete(0, 'end')
                    self.ptt_entry.insert(0, keys_text)
                else:
                    self.toggle_entry.delete(0, 'end')
                    self.toggle_entry.insert(0, keys_text)
        except Exception as e:
            logger.error(f"Error during key recording: {e}")

    def _on_key_release(self, key):
        """Handle key release during recording"""
        # Auto-stop when all keys are released
        if len(self.current_keys) > 0:
            threading.Timer(0.5, self._check_recording_completion).start()

    def _check_recording_completion(self):
        """Check if recording should be completed"""
        if self.recording_hotkey and len(self.current_keys) > 0:
            self.stop_recording_hotkey()

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

    def save_settings(self):
        """Save hotkey settings"""
        # Save push-to-talk
        ptt_text = self.ptt_entry.get().strip()
        if ptt_text and ptt_text not in ["No keys recorded", "Press your key combination..."]:
            ptt_keys = [k.strip().lower() for k in ptt_text.split(" + ") if k.strip()]
            self.config.set('hotkeys.push_to_talk', ptt_keys)

        # Save toggle recording
        toggle_text = self.toggle_entry.get().strip()
        if toggle_text and toggle_text not in ["No keys recorded", "Press your key combination..."]:
            toggle_keys = [k.strip().lower() for k in toggle_text.split(" + ") if k.strip()]
            self.config.set('hotkeys.toggle_recording', toggle_keys)

    def cleanup(self):
        """Cleanup resources"""
        if self.key_listener:
            self.key_listener.stop()

class AudioTab:
    """Audio configuration tab"""

    def __init__(self, tab, config, app):
        self.tab = tab
        self.config = config
        self.app = app
        self.setup_tab()

    def setup_tab(self):
        """Setup audio tab"""
        # Device selection
        device_frame = ctk.CTkFrame(self.tab)
        device_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(device_frame, text="Audio Input Device:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        devices = self.app.audio_recorder.get_audio_devices()
        device_names = [f"{d['name']} ({d['channels']} ch)" for d in devices]

        self.device_combo = ctk.CTkComboBox(device_frame, values=device_names if device_names else ["Default"])
        self.device_combo.pack(fill="x", padx=10, pady=5)

        # Sample rate
        rate_frame = ctk.CTkFrame(self.tab)
        rate_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(rate_frame, text="Sample Rate:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)
        self.sample_rate_combo = ctk.CTkComboBox(rate_frame, values=["8000", "16000", "22050", "44100", "48000"])
        self.sample_rate_combo.pack(fill="x", padx=10, pady=5)
        self.sample_rate_combo.set(str(self.config.get('audio.sample_rate', 16000)))

        # Voice activation threshold
        threshold_frame = ctk.CTkFrame(self.tab)
        threshold_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(threshold_frame, text="Voice Activation Threshold:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        self.threshold_slider = ctk.CTkSlider(threshold_frame, from_=0.005, to=0.1, number_of_steps=19)
        self.threshold_slider.pack(fill="x", padx=10, pady=5)
        self.threshold_slider.set(self.config.get('audio.voice_activation_threshold', 0.02))

        self.threshold_label = ctk.CTkLabel(threshold_frame, text="0.02")
        self.threshold_label.pack(padx=10, pady=2)
        self.threshold_slider.configure(command=self.update_threshold_label)

    def update_threshold_label(self, value):
        """Update threshold label"""
        self.threshold_label.configure(text=f"{value:.3f}")

    def save_settings(self):
        """Save audio settings"""
        self.config.set('audio.sample_rate', int(self.sample_rate_combo.get()))
        self.config.set('audio.voice_activation_threshold', self.threshold_slider.get())

class WhisperTab:
    """Whisper configuration tab"""

    def __init__(self, tab, config):
        self.tab = tab
        self.config = config
        self.setup_tab()

    def setup_tab(self):
        """Setup whisper tab"""
        # Model size
        model_frame = ctk.CTkFrame(self.tab)
        model_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(model_frame, text="Whisper Model Size:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        model_options = [
            "tiny - Fastest, least accurate (39 MB)",
            "base - Good balance (74 MB)",
            "small - Better accuracy (244 MB)",
            "medium - High accuracy (769 MB)",
            "large - Best accuracy (1550 MB)"
        ]

        self.model_combo = ctk.CTkComboBox(model_frame, values=model_options)
        self.model_combo.pack(fill="x", padx=10, pady=5)

        current_model = self.config.get('whisper.model_size', 'base')
        for option in model_options:
            if option.startswith(current_model):
                self.model_combo.set(option)
                break

        # Language
        lang_frame = ctk.CTkFrame(self.tab)
        lang_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(lang_frame, text="Language:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        languages = [
            "auto - Auto-detect",
            "en - English",
            "es - Spanish",
            "fr - French",
            "de - German",
            "it - Italian",
            "pt - Portuguese",
            "ru - Russian",
            "ja - Japanese",
            "ko - Korean",
            "zh - Chinese",
            "ar - Arabic",
            "hi - Hindi",
            "te - Telugu",
            "tr - Turkish"
        ]

        self.language_combo = ctk.CTkComboBox(lang_frame, values=languages)
        self.language_combo.pack(fill="x", padx=10, pady=5)

        current_lang = self.config.get('whisper.language', 'auto')
        for lang in languages:
            if lang.startswith(current_lang):
                self.language_combo.set(lang)
                break

        # Task
        task_frame = ctk.CTkFrame(self.tab)
        task_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(task_frame, text="Task:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)
        self.task_combo = ctk.CTkComboBox(task_frame, values=["transcribe", "translate"])
        self.task_combo.pack(fill="x", padx=10, pady=5)
        self.task_combo.set(self.config.get('whisper.task', 'transcribe'))

    def save_settings(self):
        """Save whisper settings"""
        # Extract model size from selection
        model_selection = self.model_combo.get()
        model_size = model_selection.split(' ')[0]
        self.config.set('whisper.model_size', model_size)

        # Extract language code
        lang_selection = self.language_combo.get()
        lang_code = lang_selection.split(' ')[0]
        self.config.set('whisper.language', lang_code)

        self.config.set('whisper.task', self.task_combo.get())

class VoiceAssistantTab:
    """Voice assistant configuration tab"""

    def __init__(self, tab, config):
        self.tab = tab
        self.config = config
        self.setup_tab()

    def setup_tab(self):
        """Setup voice assistant tab"""
        # Enable/disable
        self.va_enabled = ctk.CTkSwitch(self.tab, text="Enable 'Hey Soffy' Voice Assistant", font=ctk.CTkFont(size=14, weight="bold"))
        self.va_enabled.pack(anchor="w", padx=10, pady=15)
        if self.config.get('voice_assistant.enabled', True):
            self.va_enabled.select()

        # Wake word
        wake_frame = ctk.CTkFrame(self.tab)
        wake_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(wake_frame, text="Wake Word:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)
        self.wake_word_entry = ctk.CTkEntry(wake_frame, placeholder_text="hey soffy")
        self.wake_word_entry.pack(fill="x", padx=10, pady=5)
        self.wake_word_entry.insert(0, self.config.get('voice_assistant.wake_word', 'hey soffy'))

        # Sensitivity
        sens_frame = ctk.CTkFrame(self.tab)
        sens_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(sens_frame, text="Detection Sensitivity:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        self.sensitivity_slider = ctk.CTkSlider(sens_frame, from_=0.1, to=1.0, number_of_steps=9)
        self.sensitivity_slider.pack(fill="x", padx=10, pady=5)
        self.sensitivity_slider.set(self.config.get('voice_assistant.sensitivity', 0.5))

        self.sensitivity_label = ctk.CTkLabel(sens_frame, text="0.5")
        self.sensitivity_label.pack(padx=10, pady=2)
        self.sensitivity_slider.configure(command=self.update_sensitivity_label)

        # Auto-stop timeout
        timeout_frame = ctk.CTkFrame(self.tab)
        timeout_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(timeout_frame, text="Auto-stop Timeout (seconds):", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        self.timeout_slider = ctk.CTkSlider(timeout_frame, from_=1.0, to=10.0, number_of_steps=18)
        self.timeout_slider.pack(fill="x", padx=10, pady=5)
        self.timeout_slider.set(self.config.get('voice_assistant.auto_stop_timeout', 3.0))

        self.timeout_label = ctk.CTkLabel(timeout_frame, text="3.0")
        self.timeout_label.pack(padx=10, pady=2)
        self.timeout_slider.configure(command=self.update_timeout_label)

    def update_sensitivity_label(self, value):
        """Update sensitivity label"""
        self.sensitivity_label.configure(text=f"{value:.1f}")

    def update_timeout_label(self, value):
        """Update timeout label"""
        self.timeout_label.configure(text=f"{value:.1f}")

    def save_settings(self):
        """Save voice assistant settings"""
        self.config.set('voice_assistant.enabled', bool(self.va_enabled.get()))
        self.config.set('voice_assistant.wake_word', self.wake_word_entry.get().lower().strip())
        self.config.set('voice_assistant.sensitivity', self.sensitivity_slider.get())
        self.config.set('voice_assistant.auto_stop_timeout', self.timeout_slider.get())

class BehaviorTab:
    """Behavior configuration tab"""

    def __init__(self, tab, config):
        self.tab = tab
        self.config = config
        self.setup_tab()

    def setup_tab(self):
        """Setup behavior tab"""
        # Text processing
        processing_frame = ctk.CTkFrame(self.tab)
        processing_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(processing_frame, text="Text Processing:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        self.auto_punctuation = ctk.CTkCheckBox(processing_frame, text="Add automatic punctuation")
        self.auto_punctuation.pack(anchor="w", padx=10, pady=3)
        if self.config.get('behavior.auto_punctuation', True):
            self.auto_punctuation.select()

        self.capitalize_sentences = ctk.CTkCheckBox(processing_frame, text="Capitalize sentences")
        self.capitalize_sentences.pack(anchor="w", padx=10, pady=3)
        if self.config.get('behavior.capitalize_sentences', True):
            self.capitalize_sentences.select()

        self.remove_filler_words = ctk.CTkCheckBox(processing_frame, text="Remove filler words (um, uh, etc.)")
        self.remove_filler_words.pack(anchor="w", padx=10, pady=3)
        if self.config.get('behavior.remove_filler_words', True):
            self.remove_filler_words.select()

        # Confidence threshold
        conf_frame = ctk.CTkFrame(self.tab)
        conf_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(conf_frame, text="Confidence Threshold:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        self.confidence_slider = ctk.CTkSlider(conf_frame, from_=0.1, to=1.0, number_of_steps=9)
        self.confidence_slider.pack(fill="x", padx=10, pady=5)
        self.confidence_slider.set(self.config.get('behavior.confidence_threshold', 0.7))

        self.confidence_label = ctk.CTkLabel(conf_frame, text="0.7")
        self.confidence_label.pack(padx=10, pady=2)
        self.confidence_slider.configure(command=self.update_confidence_label)

    def update_confidence_label(self, value):
        """Update confidence label"""
        self.confidence_label.configure(text=f"{value:.1f}")

    def save_settings(self):
        """Save behavior settings"""
        self.config.set('behavior.auto_punctuation', bool(self.auto_punctuation.get()))
        self.config.set('behavior.capitalize_sentences', bool(self.capitalize_sentences.get()))
        self.config.set('behavior.remove_filler_words', bool(self.remove_filler_words.get()))
        self.config.set('behavior.confidence_threshold', self.confidence_slider.get())

class UITab:
    """UI configuration tab"""

    def __init__(self, tab, config, app):
        self.tab = tab
        self.config = config
        self.app = app
        self.setup_tab()

    def setup_tab(self):
        """Setup UI tab"""
        # Theme
        theme_frame = ctk.CTkFrame(self.tab)
        theme_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(theme_frame, text="Theme:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)
        self.theme_combo = ctk.CTkComboBox(theme_frame, values=["dark", "light", "system"])
        self.theme_combo.pack(fill="x", padx=10, pady=5)
        self.theme_combo.set(self.config.get('ui.theme', 'dark'))

        # System integration
        integration_frame = ctk.CTkFrame(self.tab)
        integration_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(integration_frame, text="System Integration:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        self.minimize_to_tray = ctk.CTkCheckBox(integration_frame, text="Minimize to system tray")
        self.minimize_to_tray.pack(anchor="w", padx=10, pady=3)
        if self.config.get('ui.minimize_to_tray', True):
            self.minimize_to_tray.select()

        self.show_notifications = ctk.CTkCheckBox(integration_frame, text="Show desktop notifications")
        self.show_notifications.pack(anchor="w", padx=10, pady=3)
        if self.config.get('ui.show_notifications', True):
            self.show_notifications.select()

        self.auto_start = ctk.CTkSwitch(integration_frame, text="Auto-start with Windows", command=self.on_auto_start_toggle)
        self.auto_start.pack(anchor="w", padx=10, pady=5)
        if self.app.auto_start_manager.is_auto_start_enabled():
            self.auto_start.select()

    def on_auto_start_toggle(self):
        """Handle auto-start toggle"""
        try:
            if self.auto_start.get():
                success = self.app.auto_start_manager.enable_auto_start()
                if not success:
                    self.auto_start.deselect()
                    messagebox.showerror("Error", "Failed to enable auto-start")
            else:
                success = self.app.auto_start_manager.disable_auto_start()
                if not success:
                    self.auto_start.select()
                    messagebox.showerror("Error", "Failed to disable auto-start")
        except Exception as e:
            logger.error(f"Auto-start toggle error: {e}")

    def save_settings(self):
        """Save UI settings"""
        old_theme = self.config.get('ui.theme')
        new_theme = self.theme_combo.get()

        self.config.set('ui.theme', new_theme)
        self.config.set('ui.minimize_to_tray', bool(self.minimize_to_tray.get()))
        self.config.set('ui.show_notifications', bool(self.show_notifications.get()))
        self.config.set('ui.auto_start', bool(self.auto_start.get()))

        # Apply theme change
        if new_theme != old_theme:
            ctk.set_appearance_mode(new_theme)

class SoundsTab:
    """Sounds configuration tab"""

    def __init__(self, tab, config):
        self.tab = tab
        self.config = config
        self.setup_tab()

    def setup_tab(self):
        """Setup sounds tab"""
        sounds_frame = ctk.CTkFrame(self.tab)
        sounds_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(sounds_frame, text="Sound Effects:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        self.sounds_enabled = ctk.CTkCheckBox(sounds_frame, text="Enable sound effects")
        self.sounds_enabled.pack(anchor="w", padx=10, pady=3)
        if self.config.get('sounds.enabled', True):
            self.sounds_enabled.select()

        self.start_sound = ctk.CTkCheckBox(sounds_frame, text="Start recording sound")
        self.start_sound.pack(anchor="w", padx=10, pady=3)
        if self.config.get('sounds.start_recording', True):
            self.start_sound.select()

        self.stop_sound = ctk.CTkCheckBox(sounds_frame, text="Stop recording sound")
        self.stop_sound.pack(anchor="w", padx=10, pady=3)
        if self.config.get('sounds.stop_recording', True):
            self.stop_sound.select()

        self.wake_word_sound = ctk.CTkCheckBox(sounds_frame, text="Wake word detected sound")
        self.wake_word_sound.pack(anchor="w", padx=10, pady=3)
        if self.config.get('sounds.wake_word_detected', True):
            self.wake_word_sound.select()

        # Volume control
        volume_frame = ctk.CTkFrame(self.tab)
        volume_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(volume_frame, text="Volume:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)

        self.volume_slider = ctk.CTkSlider(volume_frame, from_=0.1, to=1.0, number_of_steps=9)
        self.volume_slider.pack(fill="x", padx=10, pady=5)
        self.volume_slider.set(self.config.get('sounds.volume', 0.7))

        self.volume_label = ctk.CTkLabel(volume_frame, text="0.7")
        self.volume_label.pack(padx=10, pady=2)
        self.volume_slider.configure(command=self.update_volume_label)

    def update_volume_label(self, value):
        """Update volume label"""
        self.volume_label.configure(text=f"{value:.1f}")

    def save_settings(self):
        """Save sound settings"""
        self.config.set('sounds.enabled', bool(self.sounds_enabled.get()))
        self.config.set('sounds.start_recording', bool(self.start_sound.get()))
        self.config.set('sounds.stop_recording', bool(self.stop_sound.get()))
        self.config.set('sounds.wake_word_detected', bool(self.wake_word_sound.get()))
        self.config.set('sounds.volume', self.volume_slider.get())
