import sys
import logging
import os
from pathlib import Path

# Add the current directory to sys.path to allow imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt5.QtWidgets import QApplication, QMessageBox, QWizard
from PyQt5.QtGui import QIcon
from gui.wizard import SetupWizard

def setup_logging():
    """Configure application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def get_icon_path():
    """Get icon path handling both development and PyInstaller paths"""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)
        icon_path = base_path / "provus_formatter" / "assets" / "icon.ico"
    else:
        # Running in development
        # First try relative to the script
        icon_path = Path(__file__).parent / "assets" / "icon.ico"
        
        # If that doesn't exist, try the absolute path
        if not icon_path.exists():
            # Try to find it relative to the src directory
            src_path = Path(current_dir)
            icon_path = src_path / "provus_formatter" / "assets" / "icon.ico"
    
    return icon_path

def main():
    logger = setup_logging()
    try:
        app = QApplication(sys.argv)
        
        # Set application icon
        icon_path = get_icon_path()
        if icon_path.exists():
            app_icon = QIcon(str(icon_path))
            app.setWindowIcon(app_icon)
        else:
            logger.warning(f"Icon not found at {icon_path}")
        
        # Show disclaimer before creating wizard
        disclaimer = QMessageBox()
        disclaimer.setWindowTitle("Important Notice")
        disclaimer.setIcon(QMessageBox.Warning)
        if icon_path.exists():
            disclaimer.setWindowIcon(app_icon)
        
        disclaimer.setText("Disclaimer")
        disclaimer.setInformativeText(
            "This tool was developed to reduce manual file editing and creation.\n\n "
            "Users are responsible for verifying the accuracy of the generated waveform and sampling files for their specific data and requirements.\n\n "
            "Always maintain backups of original data files.\n\n"
            "If no waveform shape is defined we assume square wave, view waveform by double clicking on row or view in provus waveform tab.\n\n"
            "By using this tool, you acknowledge and accept these responsibilities."
        )
        
        # Add Ok/Cancel buttons
        disclaimer.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        disclaimer.setDefaultButton(QMessageBox.Cancel)  # Make Cancel the default for safety
        
        # Style the buttons
        ok_button = disclaimer.button(QMessageBox.Ok)
        cancel_button = disclaimer.button(QMessageBox.Cancel)
        ok_button.setText("I Accept")
        cancel_button.setText("Exit")
        
        # Show the dialog and get result
        result = disclaimer.exec_()
        
        if result == QMessageBox.Ok:
            wizard = SetupWizard()
            if icon_path.exists():
                wizard.setWindowIcon(app_icon)
            wizard.show()
            sys.exit(app.exec_())
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Application failed to start: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 