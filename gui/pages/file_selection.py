from PyQt5.QtWidgets import (QWizardPage, QVBoxLayout, QPushButton, 
                            QListWidget, QFileDialog, QLabel)
from PyQt5.QtCore import Qt, QMimeData
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class FileSelectionPage(QWizardPage):
    def __init__(self, file_data):
        super().__init__()
        self.file_data = file_data
        self.setTitle("File Selection")
        self.setSubTitle("Drag and drop .tem or .pem files and set root directory")
        
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666;")
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Add status label at top
        self.status_label.setText("Waiting for files...")
        layout.addWidget(self.status_label)
        
        # Create drop area with fixed minimum size
        self.file_list = DragDropList(self.file_data)
        self.file_list.setMinimumHeight(300)
        layout.addWidget(self.file_list)
        
        # Directory selection buttons and labels
        buttons_and_labels = self._create_directory_buttons()
        self.root_dir_btn = buttons_and_labels[0]
        self.data_dir_btn = buttons_and_labels[1]
        self.root_dir_label = buttons_and_labels[2]
        self.data_dir_label = buttons_and_labels[3]
        
        layout.addWidget(self.root_dir_btn)
        layout.addWidget(self.data_dir_btn)
        layout.addWidget(self.root_dir_label)
        layout.addWidget(self.data_dir_label)
        
        self.setLayout(layout)
        
    def _create_directory_buttons(self):
        """Create and configure directory selection buttons"""
        self.root_dir_btn = QPushButton("Set Root Directory")
        self.data_dir_btn = QPushButton("Set Data Directory")
        
        self.root_dir_btn.clicked.connect(self.set_root_dir)
        self.data_dir_btn.clicked.connect(self.set_data_dir)
        
        self.root_dir_label = QLabel("Root Directory: Not Set")
        self.data_dir_label = QLabel("Data Directory: Not Set")
        
        return (self.root_dir_btn, self.data_dir_btn, 
                self.root_dir_label, self.data_dir_label)
        
    def isComplete(self):
        """Override isComplete to enforce root directory requirement"""
        # Only check if root directory is set and files exist before allowing next
        return bool(self.file_data['root_dir'] and self.file_data['tem_files'])
        
    def set_root_dir(self):
        try:
            dir_path = QFileDialog.getExistingDirectory(self, "Select Root Directory")
            if dir_path:
                self.file_data['root_dir'] = Path(dir_path)
                self.root_dir_label.setText(f"Root Directory: {dir_path}")
                self.status_label.setText(f"Root directory set to: {dir_path}")
                self.status_label.setStyleSheet("color: #4CAF50;")
                logger.info(f"Root directory set to: {dir_path}")
                self.completeChanged.emit()
        except Exception as e:
            self.status_label.setText("Error setting root directory!")
            self.status_label.setStyleSheet("color: #f44336;")
            logger.error(f"Error setting root directory: {str(e)}", exc_info=True)
    
    def set_data_dir(self):
        try:
            dir_path = QFileDialog.getExistingDirectory(self, "Select Data Directory")
            if dir_path:
                self.file_data['data_dir'] = Path(dir_path)
                self.data_dir_label.setText(f"Data Directory: {dir_path}")
                self.scan_data_directory(dir_path)
                logger.info(f"Data directory set to: {dir_path}")
        except Exception as e:
            logger.error(f"Error setting data directory: {str(e)}", exc_info=True)
    
    def scan_data_directory(self, dir_path):
        """Scan data directory for .tem and .pem files"""
        try:
            path = Path(dir_path)
            for file_path in path.rglob("*.tem"):
                self.file_data['tem_files'].append(str(file_path))
                self.file_list.addItem(str(file_path))
            for file_path in path.rglob("*.pem"):
                self.file_data['tem_files'].append(str(file_path))
                self.file_list.addItem(str(file_path))
        except Exception as e:
            logger.error(f"Error scanning data directory: {str(e)}", exc_info=True)

class DragDropList(QListWidget):
    def __init__(self, file_data):
        super().__init__()
        self.file_data = file_data
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        
        # Set visual properties
        self.default_style = """
            QListWidget {
                border: 2px dashed #aaa;
                border-radius: 5px;
                padding: 10px;
                min-height: 200px;
                background-color: #f8f9fa;
            }
            QListWidget::item {
                padding: 5px;
            }
        """
        self.setStyleSheet(self.default_style)
        
        # Add instruction label
        self.addItem("Drag and drop .tem or .pem files here")
        self.item(0).setForeground(Qt.gray)
    
    def dragEnterEvent(self, event):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith(('.tem', '.pem')) for url in urls):
                event.accept()
                self.setStyleSheet("""
                    QListWidget {
                        border: 2px dashed #4CAF50;
                        border-radius: 5px;
                        padding: 10px;
                        min-height: 200px;
                        background-color: #e8f5e9;
                    }
                """)
                return
        event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move event"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith(('.tem', '.pem')) for url in urls):
                event.accept()
                return
        event.ignore()
    
    def dragLeaveEvent(self, event):
        """Reset styling when drag leaves"""
        self.setStyleSheet(self.default_style)
        event.accept()
    
    def dropEvent(self, event):
        """Handle file drop"""
        try:
            # Clear instruction item if it exists
            if self.count() == 1 and self.item(0).foreground() == Qt.gray:
                self.clear()
            
            files = [url.toLocalFile() for url in event.mimeData().urls()]
            valid_files = []
            
            for file_path in files:
                if file_path.lower().endswith(('.tem', '.pem')):
                    file_name = Path(file_path).name
                    
                    # Check for duplicate filenames
                    existing_files = [Path(f).name for f in self.file_data['tem_files']]
                    if file_name in existing_files:
                        logger.warning(f"Duplicate file name ignored: {file_name}")
                        continue
                        
                    self.file_data['tem_files'].append(file_path)
                    self.addItem(file_path)
                    valid_files.append(file_path)
                    logger.info(f"Added file: {file_path}")
                else:
                    logger.warning(f"Ignored non-tem/pem file: {file_path}")
            
            if valid_files:
                event.accept()
                # Check if we can proceed
                self.parent().completeChanged.emit()
            else:
                event.ignore()
                
        except Exception as e:
            logger.error(f"Error processing dropped files: {str(e)}", exc_info=True)
            event.ignore()
        
        # Reset styling
        self.setStyleSheet(self.default_style) 