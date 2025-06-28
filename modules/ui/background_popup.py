# =============================================================================
# UI MODULE - Background Popup
# File: modules/ui/background_popup.py
# =============================================================================

import customtkinter as ctk

class BackgroundPopup:
    """Background popup window"""

    def __init__(self, app):
        self.app = app
        self.popup = None
        self.is_visible = False
        self.animation_active = False
        self.animation_frame = 0
        self.drag_data = {"x": 0, "y": 0}

    def create_popup(self):
        """Create popup window"""
        if self.popup is None:
            self.popup = ctk.CTkToplevel()
            self.popup.title("")
            self.popup.geometry("200x40")
            self.popup.resizable(False, False)

            self.popup.overrideredirect(True)
            self.popup.attributes('-topmost', True)
            self.popup.attributes('-alpha', 0.9)

            # Position at bottom center
            screen_width = self.popup.winfo_screenwidth()
            x = (screen_width - 200) // 2
            self.popup.geometry(f"+{x}+700")

            # Main frame
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

            # Content
            content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
            content_frame.pack(fill="both", expand=True, padx=8, pady=6)
            content_frame.bind("<Button-1>", self.start_drag)
            content_frame.bind("<B1-Motion>", self.on_drag)

            # Left side - status
            left_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            left_frame.pack(side="left", fill="y")

            self.mic_label = ctk.CTkLabel(
                left_frame,
                text="🎤",
                font=ctk.CTkFont(size=16),
                text_color="gray"
            )
            self.mic_label.pack(side="left", pady=2)
            self.mic_label.bind("<Button-1>", self.start_drag)
            self.mic_label.bind("<B1-Motion>", self.on_drag)

            self.status_label = ctk.CTkLabel(
                left_frame,
                text="Ready",
                font=ctk.CTkFont(size=10),
                text_color="gray"
            )
            self.status_label.pack(side="left", padx=(5, 0), pady=2)
            self.status_label.bind("<Button-1>", self.start_drag)
            self.status_label.bind("<B1-Motion>", self.on_drag)

            # Right side - controls
            right_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            right_frame.pack(side="right", fill="y")

            # Settings button
            self.settings_button = ctk.CTkButton(
                right_frame,
                text="⚙",
                width=20,
                height=20,
                font=ctk.CTkFont(size=12),
                fg_color=("#444444", "#333333"),
                hover_color=("#555555", "#444444"),
                command=self.open_settings
            )
            self.settings_button.pack(side="right", padx=(0, 3))

            # Status dot
            self.status_dot = ctk.CTkLabel(
                right_frame,
                text="●",
                font=ctk.CTkFont(size=12),
                text_color="gray"
            )
            self.status_dot.pack(side="right", padx=(3, 0), pady=2)
            self.status_dot.bind("<Button-1>", self.start_drag)
            self.status_dot.bind("<B1-Motion>", self.on_drag)

            self.popup.withdraw()

    def start_drag(self, event):
        """Start dragging"""
        self.drag_data["x"] = event.x_root - self.popup.winfo_x()
        self.drag_data["y"] = event.y_root - self.popup.winfo_y()

    def on_drag(self, event):
        """Handle dragging"""
        new_x = event.x_root - self.drag_data["x"]
        new_y = event.y_root - self.drag_data["y"]

        # Keep within screen bounds
        screen_width = self.popup.winfo_screenwidth()
        screen_height = self.popup.winfo_screenheight()
        popup_width = self.popup.winfo_width()
        popup_height = self.popup.winfo_height()

        new_x = max(0, min(new_x, screen_width - popup_width))
        new_y = max(0, min(new_y, screen_height - popup_height))

        self.popup.geometry(f"+{new_x}+{new_y}")

    def open_settings(self):
        """Open settings"""
        self.app.show_window()

    def show_popup(self):
        """Show popup"""
        if self.popup is None:
            self.create_popup()
        self.popup.deiconify()
        self.popup.lift()
        self.is_visible = True

    def hide_popup(self):
        """Hide popup"""
        if self.popup:
            self.popup.withdraw()
        self.is_visible = False
        self.stop_recording_animation()

    def update_status(self, message, recording=False):
        """Update status"""
        if self.status_label:
            self.status_label.configure(text=message)

    def start_recording_animation(self):
        """Start recording animation"""
        self.animation_active = True
        self.animation_frame = 0
        self.animate_recording()

    def stop_recording_animation(self):
        """Stop recording animation"""
        self.animation_active = False
        if self.mic_label:
            self.mic_label.configure(text_color="gray")
        if self.status_dot:
            self.status_dot.configure(text_color="gray")

    def animate_recording(self):
        """Animate recording indicator"""
        if not self.animation_active or not self.popup:
            return

        colors = ["#ff4444", "#ff6666", "#ff8888", "#ffaaaa", "#ff8888", "#ff6666"]
        color = colors[self.animation_frame % len(colors)]

        if self.mic_label:
            self.mic_label.configure(text_color=color)
        if self.status_dot:
            self.status_dot.configure(text_color=color)

        self.animation_frame += 1

        if self.popup:
            self.popup.after(200, self.animate_recording)
