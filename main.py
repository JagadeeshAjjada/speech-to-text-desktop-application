# =============================================================================
# INSTALLATION GUIDE AND DIRECTORY STRUCTURE
# =============================================================================

"""
"""

# Add modules directory to path
import sys
import os
import logging
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "modules"))

# Import and run the main application
from modules.core.main_app import VoiceTypeProApp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check for required packages"""
    required_packages = [
        'whisper', 'torch', 'pyaudio', 'sounddevice', 'pynput', 
        'customtkinter', 'pystray', 'pyperclip', 'pygame', 'librosa'
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
        print(f"\nInstall with: pip install {' '.join(missing_packages)}")
        return False
    return True

def main():
    """Main entry point"""
    try:
        if not check_dependencies():
            return
        
        app = VoiceTypeProApp()
        app.run()
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
