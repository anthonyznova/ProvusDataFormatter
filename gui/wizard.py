from PyQt5.QtWidgets import QWizard, QWizardPage, QTreeWidget, QTreeWidgetItem, QHeaderView
from gui.pages.file_selection import FileSelectionPage
from gui.pages.analysis import AnalysisPage
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class SetupWizard(QWizard):
    def __init__(self):
        super().__init__()
        
        # Configure wizard appearance
        self.setWindowTitle("Provus Data Formatter")
        self.setWizardStyle(QWizard.ModernStyle)
        
        self.file_data = self._initialize_file_data()
        
        # Add pages
        self.addPage(FileSelectionPage(self.file_data))
        self.addPage(AnalysisPage(self.file_data))
        
        # Set window properties
        self.resize(1200, 600)
        
    def _initialize_file_data(self):
        """Initialize shared data storage"""
        return {
            'tem_files': [],
            'root_dir': None,
            'data_dir': None
        }

    def nextId(self):
        """Override nextId to implement custom page navigation logic"""
        current_id = self.currentId()
        
        try:
            # Validate navigation from page 1 to 2
            if current_id == 0 and not self.file_data['tem_files']:
                logger.warning("No files selected. Cannot proceed to analysis.")
                return 0
            
            return super().nextId()
            
        except Exception as e:
            logger.error(f"Navigation error: {str(e)}", exc_info=True)
            return current_id 

    def create_analysis_table(self, file_results):
        """Create analysis table with file information"""
        # Define columns
        columns = [
            'Filename',
            'Base Frequency',
            'Units',
            '# of Channels',
            'Tx Waveform',  # New column
            'Duty Cycle',   # New column
            'A Test',
            'E Test',
            'Classification'
        ]
        
        # Create table data
        table_data = []
        for file_path, result in file_results.items():
            if not result:
                continue
            
            filename = Path(file_path).name
            header_info = result.get('header_info', {})
            letter_counts = result.get('letter_counts', (0, 0))
            
            row = [
                filename,
                header_info.get('base_frequency', 'None'),
                header_info.get('units', 'None'),
                header_info.get('num_channels', 'None'),
                header_info.get('tx_waveform', 'Undefined'),  # New column
                header_info.get('duty_cycle', 'Undefined'),   # New column
                f"atest{letter_counts[0]}",
                f"etest{letter_counts[1]}",
                result.get('classification', 'None')
            ]
            table_data.append(row)
        
        # Create and configure table using PyQt5
        table = QTreeWidget()
        table.setHeaderLabels(columns)
        
        # Set column widths
        header = table.header()
        for i in range(len(columns)):
            header.resizeSection(i, 100)  # Adjust width as needed
        
        # Insert data
        for row in table_data:
            item = QTreeWidgetItem(table)
            for i, value in enumerate(row):
                item.setText(i, str(value))
        
        return table 