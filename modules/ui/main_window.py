# =============================================================================
# UI MODULE - Main Window
# File: modules/ui/main_window.py
# =============================================================================

import customtkinter as ctk
import time

class MainWindow:
    """Main application window"""

    def __init__(self, config, app):
        self.config = config
        self.app = app
        self.root = None
        self.setup_gui()

    def setup_gui(self):
        """Setup main GUI"""
        ctk.set_appearance_mode(self.config.get('ui.theme', 'dark'))
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("VoiceType Pro - Enhanced")
        self.root.geometry("850x650")
        self.root.resizable(True, True)

        # Main container
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title section
        self.setup_title_section(main_frame)

        # Status section
        self.setup_status_section(main_frame)

        # Control section
        self.setup_control_section(main_frame)

        # Hotkey display
        self.setup_hotkey_section(main_frame)

        # Transcription log
        self.setup_log_section(main_frame)

        # Event handlers
        self.root.protocol("WM_DELETE_WINDOW", self.app.on_closing)

    def setup_title_section(self, parent):
        """Setup title section"""
        title_frame = ctk.CTkFrame(parent)
        title_frame.pack(fill="x", padx=20, pady=(20, 10))

        title_label = ctk.CTkLabel(
            title_frame,
            text="VoiceType Pro - Enhanced",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(side="left", padx=20, pady=15)

        # Voice assistant status
        va_enabled = self.config.get('voice_assistant.enabled', True)
        status_text = "🎙️ Hey Soffy Active" if va_enabled else "🎙️ Hey Soffy Inactive"
        status_color = "green" if va_enabled else "gray"

        self.va_indicator = ctk.CTkLabel(
            title_frame,
            text=status_text,
            font=ctk.CTkFont(size=12),
            text_color=status_color
        )
        self.va_indicator.pack(side="right", padx=20, pady=15)

    def setup_status_section(self, parent):
        """Setup status section"""
        self.status_frame = ctk.CTkFrame(parent)
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

    def setup_control_section(self, parent):
        """Setup control section"""
        control_frame = ctk.CTkFrame(parent)
        control_frame.pack(fill="x", padx=20, pady=10)

        self.record_button = ctk.CTkButton(
            control_frame,
            text="Start Recording",
            command=self.app.toggle_recording,
            font=ctk.CTkFont(size=14)
        )
        self.record_button.pack(side="left", padx=10, pady=10)

        # Voice assistant toggle
        self.va_toggle = ctk.CTkSwitch(
            control_frame,
            text="Hey Soffy",
            command=self.toggle_voice_assistant
        )
        if self.config.get('voice_assistant.enabled', True):
            self.va_toggle.select()
        self.va_toggle.pack(side="left", padx=10, pady=10)

        settings_button = ctk.CTkButton(
            control_frame,
            text="Settings",
            command=self.app.open_settings,
            font=ctk.CTkFont(size=14)
        )
        settings_button.pack(side="right", padx=10, pady=10)

    def setup_hotkey_section(self, parent):
        """Setup hotkey display section"""
        hotkey_frame = ctk.CTkFrame(parent)
        hotkey_frame.pack(fill="x", padx=20, pady=10)

        hotkey_title = ctk.CTkLabel(
            hotkey_frame,
            text="Current Hotkeys",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        hotkey_title.pack(pady=(10, 5))

        self.hotkey_info = ctk.CTkLabel(
            hotkey_frame,
            text="",
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        self.hotkey_info.pack(padx=20, pady=(5, 15))

        self.update_hotkey_display()

    def setup_log_section(self, parent):
        """Setup transcription log"""
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

    def update_hotkey_display(self):
        """Update hotkey display"""
        ptt_keys = " + ".join(self.config.get('hotkeys.push_to_talk', [])).title()
        toggle_keys = " + ".join(self.config.get('hotkeys.toggle_recording', [])).title()

        hotkey_text = (f"Push-to-Talk: {ptt_keys}\n"
                      f"Toggle Recording: {toggle_keys}\n"
                      f"Voice Assistant: Say 'Hey Soffy'")
        self.hotkey_info.configure(text=hotkey_text)

    def toggle_voice_assistant(self):
        """Toggle voice assistant"""
        enabled = bool(self.va_toggle.get())
        self.config.set('voice_assistant.enabled', enabled)

        status_text = "🎙️ Hey Soffy Active" if enabled else "🎙️ Hey Soffy Inactive"
        status_color = "green" if enabled else "gray"
        self.va_indicator.configure(text=status_text, text_color=status_color)

        if enabled:
            self.app.hey_soffy.start_listening()
        else:
            self.app.hey_soffy.stop_listening()

    def update_status(self, message, color="white"):
        """Update status display"""
        if self.status_label:
            self.status_label.configure(text=message, text_color=color)

        # Update record button text
        if self.record_button:
            if message == "Recording...":
                self.record_button.configure(text="Stop Recording")
            elif message in ["Ready", "Text pasted successfully", "No speech detected", "No audio captured"]:
                self.record_button.configure(text="Start Recording")

    def update_recording_indicator(self, recording):
        """Update recording indicator"""
        if self.recording_indicator:
            color = "red" if recording else "gray"
            self.recording_indicator.configure(text_color=color)

    def add_transcription_to_log(self, text):
        """Add transcription to log"""
        if self.transcription_log:
            timestamp = time.strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {text}\n"
            self.transcription_log.insert("end", log_entry)
            self.transcription_log.see("end")

    def show(self):
        """Show window"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide(self):
        """Hide window"""
        self.root.withdraw()

    def quit(self):
        """Quit application"""
        if self.root:
            self.root.quit()

    def run(self):
        """Run main loop"""
        self.root.mainloop()
