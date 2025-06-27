import sys
import logging
import os
from pathlib import Path

def setup_paths():
    """Set up the Python path to find our modules"""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        base_path = sys._MEIPASS
    else:
        # Running in development
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Add the base directory and module directories to Python path
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    
    # Add core and gui to path
    for module in ['core', 'gui']:
        module_path = os.path.join(base_path, module)
        if module_path not in sys.path:
            sys.path.insert(0, module_path)

# Set up paths before any other imports
setup_paths()

from PyQt5.QtWidgets import QApplication, QMessageBox, QWizard
from PyQt5.QtGui import QIcon
from gui.wizard import SetupWizard

def setup_logging():
    """Configure application logging"""
    import tempfile
    import os
    
    # Use user's temp directory or AppData for log file
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        if os.name == 'nt':  # Windows
            log_dir = os.path.expandvars('%APPDATA%\\ProvFormatter')
        else:
            log_dir = os.path.expanduser('~/.provformatter')
        
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'app.log')
    else:
        # Running in development - use current directory
        log_path = 'app.log'
    
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler()
            ]
        )
    except PermissionError:
        # Fallback to console-only logging if file logging fails
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ]
        )
        print(f"Warning: Could not create log file at {log_path}. Using console logging only.")
    
    return logging.getLogger(__name__)

def get_icon_path():
    """Get icon path handling both development and PyInstaller paths"""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running in development
        base_path = Path(os.path.dirname(os.path.abspath(__file__)))
    
    icon_path = base_path / "assets" / "icon.ico"
    if not icon_path.exists():
        icon_path = base_path / "provus_formatter" / "assets" / "icon.ico"
    
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