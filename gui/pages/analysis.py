# --- START OF FILE analysis.py ---

from PyQt5.QtWidgets import (QWizardPage, QVBoxLayout, QPushButton,
                            QTableWidget, QTableWidgetItem, QComboBox,
                            QHBoxLayout, QHeaderView, QFileDialog, QMessageBox,
                            QLabel, QWidget, QMenu, QApplication)
import logging
from pathlib import Path
from core.file_processor import FileProcessor
from core.mcg_parser import parse_mcg_file
import re
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
import time

logger = logging.getLogger(__name__)

class AnalysisPage(QWizardPage):
    def __init__(self, file_data):
        super().__init__()
        self.file_data = file_data
        self.results = {}
        self.setTitle("Data File Parameters")
        self.setSubTitle(
            "Review the data in the table below, change the "
            "waveform, sampling and datastyle using the dropdown menus. "
            "Double click anywhere in a row to plot the corresponding waveform"
        )

        # Add flag for selection change handling
        self.ignore_selection_change = False
        
        # Add debounce timer for double-click
        self.last_double_click_time = 0
        
        # Store references to open waveform editor windows
        self._waveform_windows = []

        # Create table (placeholder, will be recreated in init_ui)
        self.table = QTableWidget()

        # Connect context menu event (will be connected in init_ui)
        # self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.table.customContextMenuRequested.connect(self.show_context_menu)

        # Create comboboxes for file selection
        self.waveform_combo = QComboBox()
        self.sampling_combo = QComboBox()
        self.data_style_combo = QComboBox()  # Add new combobox

        # Add data style options
        styles = [
            "DataFileStyleBoreholeUTEM",
            "DataFileStyleBoreholeSJV",
            "DataFileStyleCrone",
            "DataFileStyleSEM",
            "DataFileStyleDigiAtlantis"
        ]
        self.data_style_combo.addItems(styles)

        # Initialize UI
        self.init_ui()

        # Connect double-click handler instead of context menu for plotting
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

    def initializePage(self):
        """Called when page is shown"""
        # Clear previous results before processing
        self.results = {}
        self.table.setRowCount(0) # Clear table visually
        self.process_files()
        # update_table and update_dropdowns are called within process_files now

    def init_ui(self):
        layout = QVBoxLayout()

        # Add status label at top
        self.status_label = QLabel("Ready.") # Initial status
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)

        # Create table with appropriate columns
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Filename", "Base Frequency", "Units", "# of Channels",
            "Tx Waveform", "Waveform File", "Sampling File",
            "Data Style"
        ])

        # Make the entire table read-only by default, allow selection
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows) # Select whole rows
        self.table.setSelectionMode(QTableWidget.ExtendedSelection) # Allow multi-select

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # Stretch columns
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)

        # Dropdown container
        dropdown_layout = QHBoxLayout()

        # Add labels and dropdowns
        waveform_label = QLabel("Waveform File:")
        sampling_label = QLabel("Sampling File:")
        data_style_label = QLabel("Data Style:")

        dropdown_layout.addWidget(waveform_label)
        dropdown_layout.addWidget(self.waveform_combo)
        dropdown_layout.addWidget(sampling_label)
        dropdown_layout.addWidget(self.sampling_combo)
        dropdown_layout.addWidget(data_style_label)
        dropdown_layout.addWidget(self.data_style_combo)

        # Connect dropdown change events
        self.waveform_combo.currentTextChanged.connect(self.on_dropdown_changed)
        self.sampling_combo.currentTextChanged.connect(self.on_dropdown_changed)
        self.data_style_combo.currentTextChanged.connect(self.on_dropdown_changed)

        layout.addLayout(dropdown_layout)

        # Create buttons
        button_layout = QHBoxLayout()
        self.write_headers_btn = QPushButton("Update Headers")
        self.create_project_btn = QPushButton("Update Project File")
        self.import_file_btn = QPushButton("Import from .mcg")

        self.write_headers_btn.clicked.connect(self.write_headers)
        self.create_project_btn.clicked.connect(self.create_project_file)
        self.import_file_btn.clicked.connect(self.import_from_mcg)

        button_layout.addWidget(self.write_headers_btn)
        button_layout.addWidget(self.create_project_btn)
        button_layout.addWidget(self.import_file_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def on_selection_changed(self):
        """Update dropdowns when table selection changes"""
        if self.ignore_selection_change:
            return

        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            # Clear dropdowns if nothing is selected
            self.waveform_combo.setCurrentIndex(-1)
            self.sampling_combo.setCurrentIndex(-1)
            self.data_style_combo.setCurrentIndex(-1)
            return

        # If multiple rows selected, show common value or placeholder
        first_row = next(iter(selected_rows)) # Get one representative row
        waveform_file = self.table.item(first_row, 5).text()
        sampling_file = self.table.item(first_row, 6).text()
        data_style = self.table.item(first_row, 7).text()

        all_same = True
        if len(selected_rows) > 1:
            for row in selected_rows:
                if (self.table.item(row, 5).text() != waveform_file or
                    self.table.item(row, 6).text() != sampling_file or
                    self.table.item(row, 7).text() != data_style):
                    all_same = False
                    break

        # Temporarily block signals to avoid recursive updates
        self.ignore_selection_change = True
        self.waveform_combo.blockSignals(True)
        self.sampling_combo.blockSignals(True)
        self.data_style_combo.blockSignals(True)

        if all_same:
            self.waveform_combo.setCurrentText(waveform_file)
            self.sampling_combo.setCurrentText(sampling_file)
            self.data_style_combo.setCurrentText(data_style)
        else:
            # Indicate mixed selection (e.g., set to blank or a placeholder)
            self.waveform_combo.setCurrentIndex(-1) # Or set placeholder text
            self.sampling_combo.setCurrentIndex(-1)
            self.data_style_combo.setCurrentIndex(-1)
            # self.waveform_combo.setPlaceholderText("Multiple Values") # If desired

        self.waveform_combo.blockSignals(False)
        self.sampling_combo.blockSignals(False)
        self.data_style_combo.blockSignals(False)
        self.ignore_selection_change = False

    def on_dropdown_changed(self, value):
        """Handle dropdown selection changes"""
        if self.ignore_selection_change:
            return

        try:
            selected_rows = set(item.row() for item in self.table.selectedItems())
            if not selected_rows:
                return # Do nothing if no rows are selected

            sender = self.sender()
            column = -1

            if sender == self.waveform_combo:
                column = 5
                key_name = 'waveform_file' # Key for self.results dict
            elif sender == self.sampling_combo:
                column = 6
                key_name = 'sampling_file' # Key for self.results dict
            elif sender == self.data_style_combo:
                column = 7
                key_name = 'data_style' # Key for self.results dict
            else:
                return # Should not happen

            if column != -1 and value: # Only update if value is not empty/placeholder
                logger.info(f"Updating column {column} for {len(selected_rows)} rows to '{value}'")
                for row in selected_rows:
                    # Update table visually
                    current_item = self.table.item(row, column)
                    if current_item:
                        current_item.setText(value)
                    else:
                        # Should ideally not happen if table is populated correctly
                        self.table.setItem(row, column, QTableWidgetItem(value))

                    # Update internal results dictionary
                    file_path = self.table.item(row, 0).data(Qt.UserRole)
                    if file_path in self.results and self.results[file_path]:
                        self.results[file_path][key_name] = value
                        logger.debug(f"Updated results for {Path(file_path).name}: {key_name} = {value}")
                    else:
                         logger.warning(f"Could not find results entry for file: {file_path} at row {row}")

                # Optional: Re-select rows visually after update if needed
                # self.ignore_selection_change = True # Block again
                # self.table.clearSelection()
                # for row in selected_rows:
                #    self.table.selectRow(row)
                # self.ignore_selection_change = False
                self.on_selection_changed() # Refresh dropdowns based on new state

        except Exception as e:
            logger.error(f"Error handling dropdown change: {str(e)}", exc_info=True)
            # Ensure signals are unblocked in case of error
            self.waveform_combo.blockSignals(False)
            self.sampling_combo.blockSignals(False)
            self.data_style_combo.blockSignals(False)
            self.ignore_selection_change = False


    def import_from_mcg(self):
        """Import waveform and sampling files from MCG"""
        try:
            mcg_file, _ = QFileDialog.getOpenFileName(
                self, "Select MCG File", str(self.file_data.get('root_dir', '')), "MCG Files (*.mcg)" # Start in root_dir
            )

            if mcg_file:
                # Use the application's root directory for export
                export_dir = self.file_data.get('root_dir')
                if not export_dir:
                    self._handle_error("Root Directory Not Set", ValueError("Please set the root directory before importing MCG files."))
                    return

                # Process MCG file (core.mcg_parser handles file writing)
                parse_mcg_file(mcg_file, export_dir)

                # --- Refresh dropdowns WITHOUT changing selection ---
                self.ignore_selection_change = True # Prevent selection change handler

                # Store current selections
                selected_rows = set(item.row() for item in self.table.selectedItems())
                current_waveform = self.waveform_combo.currentText()
                current_sampling = self.sampling_combo.currentText()
                current_style = self.data_style_combo.currentText()

                # Update dropdown menus with potentially new files
                self.update_dropdowns()

                # Restore previous selections if possible
                waveform_index = self.waveform_combo.findText(current_waveform)
                sampling_index = self.sampling_combo.findText(current_sampling)
                style_index = self.data_style_combo.findText(current_style)

                if not selected_rows: # If nothing was selected, don't force a selection
                    self.waveform_combo.setCurrentIndex(-1)
                    self.sampling_combo.setCurrentIndex(-1)
                    self.data_style_combo.setCurrentIndex(-1)
                else: # Restore previous selection
                     if waveform_index >= 0: self.waveform_combo.setCurrentIndex(waveform_index)
                     else: self.waveform_combo.setCurrentIndex(-1) # Clear if not found
                     if sampling_index >= 0: self.sampling_combo.setCurrentIndex(sampling_index)
                     else: self.sampling_combo.setCurrentIndex(-1)
                     if style_index >= 0: self.data_style_combo.setCurrentIndex(style_index)
                     else: self.data_style_combo.setCurrentIndex(-1) # Should always be found

                self.ignore_selection_change = False # Allow selection handler again
                # --- End Refresh dropdowns ---

                mcg_name = Path(mcg_file).name
                QMessageBox.information(
                    self, "Import Successful",
                    f"CSV files successfully created from {mcg_name} in\n{export_dir / 'Provus_Options'}",
                    QMessageBox.Ok
                )

        except Exception as e:
            self.ignore_selection_change = False # Ensure reset on error
            self._handle_error("Error Importing MCG File", e)

    def process_files(self):
        """Process all files and store results"""
        try:
            root_dir = self.file_data.get('root_dir')
            if not root_dir:
                self.status_label.setText("Error: Root directory not set.")
                self.status_label.setStyleSheet("color: #f44336;") # Red
                return
            if not self.file_data.get('tem_files'):
                self.status_label.setText("No data files selected or dropped.")
                self.status_label.setStyleSheet("color: #ff9800;") # Orange
                return

            self.status_label.setText("Processing files...")
            self.status_label.setStyleSheet("color: #1976D2;") # Blue
            QApplication.processEvents() # Update UI

            processor = FileProcessor(root_dir)
            self.results = {} # Clear previous results

            # Define output directories
            provus_options_dir = Path(root_dir) / "Provus_Options"
            waveform_dir = provus_options_dir / "Waveforms"
            sampling_dir = provus_options_dir / "Channel_Sampling_Schemes"
            waveform_dir.mkdir(parents=True, exist_ok=True)
            sampling_dir.mkdir(parents=True, exist_ok=True)

            total_files = len(self.file_data['tem_files'])
            for i, file_path_str in enumerate(self.file_data['tem_files']):
                path = Path(file_path_str)
                self.status_label.setText(f"Processing file {i+1}/{total_files}: {path.name}")
                QApplication.processEvents() # Update UI

                if path.suffix.lower() == '.tem':
                    # Process TEM files
                    header_data = processor.parse_file_headers(file_path_str)
                    if header_data:
                        # Generate waveform CSV (using parsed header data)
                        waveform_file = processor._generate_waveform_csv(header_data, waveform_dir)
                        if waveform_file:
                            # Generate sampling CSV (using parsed header data)
                            sampling_file = processor._generate_sampling_csv(header_data, waveform_file, sampling_dir)
                            if sampling_file:
                                # Determine data style based on waveform/units etc.
                                tx_waveform = header_data.get('tx_waveform', 'Undefined')
                                if tx_waveform == 'UTEM': data_style = "DataFileStyleBoreholeUTEM"
                                else: data_style = "DataFileStyleBoreholeSJV" # Default for TEM

                                # Store results for TEM file
                                self.results[file_path_str] = {
                                    'base_frequency': header_data.get('base_frequency', 'N/A'),
                                    'units': header_data.get('units', 'N/A'),
                                    'num_channels': header_data.get('num_channels', 'N/A'), # Should be int or N/A
                                    'tx_waveform': tx_waveform,
                                    'duty_cycle': header_data.get('duty_cycle'), # Keep for potential later use
                                    'waveform_file': waveform_file,
                                    'sampling_file': sampling_file,
                                    'data_style': data_style,
                                    'file_type': 'TEM' # Add file type marker
                                }
                            else: logger.error(f"Failed to generate sampling file for {path.name}")
                        else: logger.error(f"Failed to generate waveform file for {path.name}")
                    else: logger.error(f"Failed to parse headers for {path.name}")


                elif path.suffix.lower() == '.pem':
                    # Process PEM files
                    try:
                        # Parse the PEM file
                        base_freq, ramp_time_sec, units, time_windows_sec, num_gates = processor.parse_pem_file(file_path_str)
                        base_name = path.stem

                        # Generate generic waveform filename (not file-specific)
                        generic_waveform_name = f"Crone_{base_freq:.1f}Hz.csv"
                        generic_sampling_name = f"Crone_{base_freq:.1f}_{num_gates}ch.csv"
                        
                        # Check if these generic files already exist
                        waveform_file_path = waveform_dir / generic_waveform_name
                        sampling_file_path = sampling_dir / generic_sampling_name
                        
                        # Only generate waveform file if it doesn't exist
                        if waveform_file_path.exists():
                            logger.info(f"Using existing waveform file: {generic_waveform_name}")
                            waveform_file = generic_waveform_name
                        else:
                            # Generate new waveform file
                            waveform_file = processor.generate_pem_waveform_csv(base_name, base_freq, ramp_time_sec, waveform_file_path)
                            logger.info(f"Generated new waveform file: {waveform_file}")

                        if waveform_file:
                            # Only generate sampling file if it doesn't exist
                            if sampling_file_path.exists():
                                logger.info(f"Using existing sampling file: {generic_sampling_name}")
                                sampling_file = generic_sampling_name
                            else:
                                # Generate new sampling file
                                sampling_file = processor.generate_pem_sampling_csv(base_name, time_windows_sec, num_gates, units, sampling_file_path)
                                logger.info(f"Generated new sampling file: {sampling_file}")

                            if sampling_file:
                                # Store results for PEM file
                                self.results[file_path_str] = {
                                    'base_frequency': f"{base_freq:.1f}", # Format frequency
                                    'units': units if units else 'N/A', # Use parsed units
                                    'num_channels': num_gates, # Use parsed num_gates
                                    'tx_waveform': 'Crone', # PEM files are treated as Crone type
                                    'duty_cycle': None, # Not applicable to standard Crone PEM
                                    'waveform_file': waveform_file,
                                    'sampling_file': sampling_file,
                                    'data_style': "DataFileStyleCrone", # PEM default
                                    'file_type': 'PEM' # Add file type marker
                                }
                                logger.info(f"Successfully processed PEM file: {path.name}")
                                logger.info(f"  Waveform file: {waveform_file}")
                                logger.info(f"  Sampling file: {sampling_file}")
                            else: 
                                logger.error(f"Failed to generate PEM sampling file for {path.name}")
                        else: 
                            logger.error(f"Failed to generate PEM waveform file for {path.name}")

                    except Exception as e:
                        logger.error(f"Error processing PEM file {path.name}: {str(e)}", exc_info=True)
                        self.results[file_path_str] = None # Mark as failed

            # After processing all files:
            self.update_table() # Update table with results
            self.update_dropdowns() # Update dropdown options
            self.status_label.setText(f"Processing complete. Reviewed {len(self.results)} files.")
            self.status_label.setStyleSheet("color: #4CAF50;") # Green

        except Exception as e:
            self._handle_error("Error during file processing", e)


    def _handle_error(self, message, error):
        """Centralized error handling and display"""
        logger.error(f"{message}: {str(error)}", exc_info=True)
        self.status_label.setText(f"Error: {message}!")
        self.status_label.setStyleSheet("color: #f44336;") # Red

        error_msg = QMessageBox(self) # Ensure parent is set
        error_msg.setIcon(QMessageBox.Critical)
        error_msg.setWindowTitle("Processing Error")
        error_msg.setText(f"An error occurred: {message}")
        # Provide more detail in the informative text, including traceback if possible
        import traceback
        detailed_error = f"{str(error)}\n\nTraceback:\n{traceback.format_exc()}"
        # Limit length to prevent overly large dialogs
        max_len = 1000
        informative_text = detailed_error[:max_len] + ('...' if len(detailed_error) > max_len else '')
        error_msg.setInformativeText(informative_text)
        error_msg.setStandardButtons(QMessageBox.Ok)
        error_msg.exec_()

    def update_table(self):
        """Update table with current results"""
        try:
            # Block signals during update to prevent issues
            self.table.blockSignals(True)
            self.table.setRowCount(0) # Clear existing rows
            self.table.setRowCount(len(self.results))

            valid_results = {k: v for k, v in self.results.items() if v is not None}
            self.table.setRowCount(len(valid_results)) # Set row count based on valid results

            for row, (file_path, result_data) in enumerate(valid_results.items()):
                filename = Path(file_path).name

                # --- Create Items (ensure they are not editable) ---
                filename_item = QTableWidgetItem(filename)
                filename_item.setData(Qt.UserRole, file_path) # Store full path
                filename_item.setFlags(filename_item.flags() ^ Qt.ItemIsEditable) # Make read-only

                freq_item = QTableWidgetItem(str(result_data.get('base_frequency', 'N/A')))
                freq_item.setFlags(freq_item.flags() ^ Qt.ItemIsEditable)

                units_item = QTableWidgetItem(str(result_data.get('units', 'N/A')))
                units_item.setFlags(units_item.flags() ^ Qt.ItemIsEditable)

                channels_item = QTableWidgetItem(str(result_data.get('num_channels', 'N/A')))
                channels_item.setFlags(channels_item.flags() ^ Qt.ItemIsEditable)

                tx_waveform_item = QTableWidgetItem(str(result_data.get('tx_waveform', 'N/A')))
                tx_waveform_item.setFlags(tx_waveform_item.flags() ^ Qt.ItemIsEditable)

                waveform_item = QTableWidgetItem(str(result_data.get('waveform_file', 'N/A')))
                waveform_item.setFlags(waveform_item.flags() ^ Qt.ItemIsEditable)

                sampling_item = QTableWidgetItem(str(result_data.get('sampling_file', 'N/A')))
                sampling_item.setFlags(sampling_item.flags() ^ Qt.ItemIsEditable)

                data_style_item = QTableWidgetItem(str(result_data.get('data_style', 'N/A')))
                data_style_item.setFlags(data_style_item.flags() ^ Qt.ItemIsEditable)

                # --- Set Items in Table ---
                self.table.setItem(row, 0, filename_item)
                self.table.setItem(row, 1, freq_item)
                self.table.setItem(row, 2, units_item)
                self.table.setItem(row, 3, channels_item)
                self.table.setItem(row, 4, tx_waveform_item)
                self.table.setItem(row, 5, waveform_item)
                self.table.setItem(row, 6, sampling_item)
                self.table.setItem(row, 7, data_style_item)

            # Resize columns after populating
            # self.table.resizeColumnsToContents() # Can make columns narrow
            # self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # Keep stretch


        except Exception as e:
            logger.error(f"Error updating table: {str(e)}", exc_info=True)
        finally:
             self.table.blockSignals(False) # Re-enable signals


    def update_dropdowns(self):
        """Update dropdown menus with available options from Provus_Options"""
        try:
            self.waveform_combo.blockSignals(True)
            self.sampling_combo.blockSignals(True)

            self.waveform_combo.clear()
            self.sampling_combo.clear()

            root_dir = self.file_data.get('root_dir')
            if not root_dir: return # Cannot proceed without root dir

            waveform_dir = Path(root_dir) / "Provus_Options" / "Waveforms"
            sampling_dir = Path(root_dir) / "Provus_Options" / "Channel_Sampling_Schemes"

            # Add files to dropdowns if directories exist and contain CSVs
            if waveform_dir.exists():
                waveform_files = sorted([f.name for f in waveform_dir.glob('*.csv')])
                if waveform_files: self.waveform_combo.addItems(waveform_files)
                logger.info(f"Found {len(waveform_files)} waveform files in {waveform_dir}")

            if sampling_dir.exists():
                sampling_files = sorted([f.name for f in sampling_dir.glob('*.csv')])
                if sampling_files: self.sampling_combo.addItems(sampling_files)
                logger.info(f"Found {len(sampling_files)} sampling files in {sampling_dir}")

            # Set dropdowns to blank initially
            self.waveform_combo.setCurrentIndex(-1)
            self.sampling_combo.setCurrentIndex(-1)

        except Exception as e:
            logger.error(f"Error updating dropdowns: {str(e)}", exc_info=True)
        finally:
             self.waveform_combo.blockSignals(False)
             self.sampling_combo.blockSignals(False)


    def write_headers(self):
        """Write WAVEFORM and SAMPLING headers to TEM data files"""
        try:
            root_dir = self.file_data.get('root_dir')
            if not root_dir:
                 self._handle_error("Cannot Update Headers", ValueError("Root directory not set."))
                 return

            self.status_label.setText("Updating headers...")
            self.status_label.setStyleSheet("color: #1976D2;") # Blue
            QApplication.processEvents()

            updated_count = 0
            skipped_count = 0
            error_count = 0
            total_rows = self.table.rowCount()

            # Use the data currently displayed in the table
            for row in range(total_rows):
                try:
                    file_path = self.table.item(row, 0).data(Qt.UserRole)
                    filename = Path(file_path).name
                    file_type = Path(file_path).suffix.lower()
                    
                    # Check if file exists and is writable
                    if not Path(file_path).exists():
                        logger.error(f"File not found: {file_path}")
                        error_count += 1
                        continue
                    
                    try:
                        # Check if file is writable by attempting to open it for writing
                        with open(file_path, 'a'):
                            pass
                    except PermissionError:
                        logger.error(f"Permission denied: Cannot write to {file_path}")
                        error_count += 1
                        continue
                    except Exception as access_err:
                        logger.error(f"Error accessing file {file_path}: {str(access_err)}")
                        error_count += 1
                        continue

                    # Process TEM files
                    if file_type == '.tem':
                        # Only process .tem files
                        waveform_file = self.table.item(row, 5).text()
                        sampling_file = self.table.item(row, 6).text()

                        if not waveform_file or not sampling_file or waveform_file == 'N/A' or sampling_file == 'N/A':
                            logger.warning(f"Skipping header update for {filename}: Waveform or Sampling file not assigned in table.")
                            skipped_count +=1
                            continue

                        # Get names without .csv extension
                        waveform_name = Path(waveform_file).stem
                        sampling_name = Path(sampling_file).stem

                        logger.info(f"Updating header for: {filename} -> WAVEFORM: {waveform_name}, SAMPLING: {sampling_name}")

                        # Read the file content
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()

                        header_modified = False
                        
                        # Find the line containing BASEFREQ, BFREQ, or BASEFREQUENCY - this is where tags should be added
                        basefreq_keywords = ['BASEFREQ', 'BFREQ', 'BASEFREQUENCY']
                        basefreq_line_index = -1
                        
                        for i, line in enumerate(lines):
                            line_upper = line.upper()
                            if any(keyword in line_upper for keyword in basefreq_keywords):
                                basefreq_line_index = i
                                logger.debug(f"Found BASEFREQ line at index {i}: {line.strip()}")
                                break
                        
                        # If no BASEFREQ line found, fall back to finding any header line
                        if basefreq_line_index == -1:
                            header_keywords = ['UNITS', 'TXWAVEFORM', 'DUTYCYCLE', 'INSTRUMENT', 'SYSTEM', 'CONFIG', 'DATATYPE', 'OFFTIME']
                            for i, line in enumerate(lines):
                                line_upper = line.upper()
                                if any(keyword in line_upper for keyword in header_keywords):
                                    basefreq_line_index = i
                                    logger.debug(f"No BASEFREQ line found, using alternative header line: {line.strip()}")
                                    break
                        
                        # If still no suitable line found, use first non-empty line 
                        if basefreq_line_index == -1:
                            for i, line in enumerate(lines):
                                if line.strip():
                                    basefreq_line_index = i
                                    logger.debug(f"Using first non-empty line: {line.strip()}")
                                    break
                                    
                        if basefreq_line_index == -1:
                            logger.warning(f"Could not find a suitable header line to append WAVEFORM/SAMPLING info in {filename}. Skipping.")
                            error_count += 1
                            continue
                        
                        # Prepare the new tags to add/update
                        new_tags = f" WAVEFORM:{waveform_name} SAMPLING:{sampling_name}" # Leading space

                        target_line_index = basefreq_line_index
                        target_line = lines[target_line_index].rstrip() # Work with line without newline
                        
                        # Log the line before modification
                        logger.debug(f"Original line: '{target_line}'")
                        
                        # Check if the tags already exist in the line
                        waveform_tag = f"WAVEFORM:{waveform_name}"
                        sampling_tag = f"SAMPLING:{sampling_name}"
                        
                        waveform_exists = waveform_tag in target_line
                        sampling_exists = sampling_tag in target_line
                        
                        if waveform_exists and sampling_exists:
                            logger.info(f"Both WAVEFORM and SAMPLING tags already exist in {filename}, skipping")
                            skipped_count += 1
                            continue
                            
                        # Remove existing WAVEFORM/SAMPLING tags if they exist but with different values
                        if "WAVEFORM:" in target_line and not waveform_exists:
                            target_line = re.sub(r'\s+WAVEFORM:[^\s&]+', '', target_line)
                            
                        if "SAMPLING:" in target_line and not sampling_exists:
                            target_line = re.sub(r'\s+SAMPLING:[^\s&]+', '', target_line)
                        
                        # Direct approach: Always add to end
                        if target_line.endswith('&'):
                            target_line = target_line[:-1].rstrip() # Remove '&' and space before it
                            target_line += new_tags + " &" # Add tags and put '&' back
                        else:
                            target_line += new_tags # Append tags directly
                        
                        # Log the final modified line
                        logger.debug(f"Modified line: '{target_line}'")

                        # Update the line in the list
                        lines[target_line_index] = target_line + "\n"
                        header_modified = True

                        # Write modified content back to file with binary mode to preserve encoding
                        if header_modified:
                            try:
                                # Write file in binary mode to preserve exact bytes
                                with open(file_path, 'wb') as f:
                                    # Join lines with proper line endings and encode
                                    content = ''.join(lines).encode('utf-8')
                                    f.write(content)
                                updated_count += 1
                                logger.info(f"Successfully updated header in {filename}")
                            except Exception as write_err:
                                logger.error(f"Error writing to file {filename}: {str(write_err)}")
                                error_count += 1
                        else:
                             logger.warning(f"No suitable line found to modify header in {filename}")
                             skipped_count += 1 # Count as skipped if no modification point found
                    
                    # Process PEM files
                    elif file_type == '.pem':
                        logger.info(f"Processing PEM file: {filename}")
                        
                        # Read the file content
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                        
                        # 1. Remove empty coordinate lines (those with <P0x> followed immediately by ~)
                        modified_lines = []
                        empty_coordinate_pattern = re.compile(r'<P\d+>\s+~')
                        for line in lines:
                            # Skip empty coordinate lines
                            if empty_coordinate_pattern.match(line.strip()):
                                logger.info(f"Removing empty coordinate line: {line.strip()}")
                                continue
                            modified_lines.append(line)
                        
                        # 2. Check for and add UUID if needed
                        has_uuid = False
                        last_p_index = -1
                        
                        # Find the last P line and check if UUID exists
                        for i, line in enumerate(modified_lines):
                            if line.strip().startswith('<P'):
                                last_p_index = i
                            elif line.strip().startswith('<MOD>uuid='):
                                has_uuid = True
                        
                        # Generate and add UUID if needed
                        if not has_uuid and last_p_index >= 0:
                            import uuid
                            # Generate a random UUID and format it as a hex string without dashes
                            new_uuid = uuid.uuid4().hex
                            uuid_line = f"<MOD>uuid={new_uuid}\n"
                            logger.info(f"Adding UUID line after coordinate info: {uuid_line.strip()}")
                            modified_lines.insert(last_p_index + 1, uuid_line)
                        
                        # Write modified content back to file
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.writelines(modified_lines)
                        updated_count += 1
                        logger.info(f"Successfully updated PEM file: {filename}")

                except Exception as ex:
                    logger.error(f"Error updating header for row {row} ({self.table.item(row, 0).text()}): {str(ex)}", exc_info=True)
                    error_count += 1

            # --- Final Status Update ---
            final_message = f"Header update complete. Updated: {updated_count}, Skipped/No Change: {skipped_count}, Errors: {error_count}"
            self.status_label.setText(final_message)
            if error_count > 0:
                 self.status_label.setStyleSheet("color: #f44336;") # Red
                 QMessageBox.warning(self, "Header Update Warning", f"{final_message}\nCheck app.log for details on errors.", QMessageBox.Ok)
            elif updated_count == 0 and skipped_count == 0:
                 self.status_label.setStyleSheet("color: #ff9800;") # Orange - Nothing to do?
                 QMessageBox.information(self, "Header Update", "No files found or no changes needed.", QMessageBox.Ok)
            else:
                 self.status_label.setStyleSheet("color: #4CAF50;") # Green
                 QMessageBox.information(self, "Header Update Success", final_message, QMessageBox.Ok)


        except Exception as e:
            self._handle_error("Error during header update process", e)

    def create_project_file(self):
        """Create or update Provus project file (*.ppf)"""
        try:
            root_path = self.file_data.get('root_dir')
            if not root_path:
                 self._handle_error("Cannot Create Project File", ValueError("Root directory not set."))
                 return

            self.status_label.setText("Updating project file...")
            self.status_label.setStyleSheet("color: #1976D2;") # Blue
            QApplication.processEvents()

            # Look for existing .ppf files
            existing_ppf = list(Path(root_path).glob('*.ppf'))
            project_file = None
            action = "created"
            if existing_ppf:
                # Simple approach: use the first one found
                project_file = existing_ppf[0]
                action = "updated"
                logger.info(f"Found existing project file, will update: {project_file}")
                # TODO: Optionally prompt user if multiple PPFs found?
            else:
                project_file = Path(root_path) / f"{Path(root_path).name}_project.ppf" # Default name
                logger.info(f"No existing project file found, creating new one: {project_file}")

            # Prepare new entries from the table data
            new_data_entries = []
            for row in range(self.table.rowCount()):
                 # Ensure items exist before accessing data/text
                 file_item = self.table.item(row, 0)
                 style_item = self.table.item(row, 7)
                 if file_item and style_item:
                     try:
                         file_path = Path(file_item.data(Qt.UserRole))
                         data_style = style_item.text()
                         if data_style and data_style != 'N/A': # Only include if style is set
                             # Get relative path from root_path
                             rel_path = file_path.relative_to(Path(root_path))
                             # Format: relative/path/to/file.ext,DataFileStyleName
                             new_data_entries.append(f"{rel_path.as_posix()},{data_style}") # Use forward slashes
                         else:
                             logger.warning(f"Skipping file {file_path.name} for project file: Data Style not set.")
                     except ValueError:
                         logger.warning(f"Could not get relative path for {file_item.data(Qt.UserRole)} relative to {root_path}")
                     except Exception as path_ex:
                          logger.error(f"Error processing row {row} for project file: {path_ex}")
                 else:
                      logger.warning(f"Missing item data for project file creation at row {row}.")


            content = []
            data_files_section_found = False
            data_files_section_start_index = -1

            # Read existing file or prepare default structure
            if project_file.exists():
                with open(project_file, 'r', encoding='utf-8') as f:
                    content = f.readlines()

                # Find the [Project Data Files] section
                for i, line in enumerate(content):
                    if '[Project Data Files]' in line:
                        data_files_section_found = True
                        data_files_section_start_index = i
                        break
            else:
                 # Default structure for new file
                 content.append('[Project Settings]\n')
                 content.append(f'Project Name="{Path(root_path).name}"\n') # Use dir name as default project name
                 content.append('\n') # Blank line before data section

            # Ensure data section exists
            if not data_files_section_found:
                 content.append('[Project Data Files]\n')
                 data_files_section_start_index = len(content) - 1
            else:
                 # Clear existing entries after the section header
                 content = content[:data_files_section_start_index + 1]

            # Add the new entries
            for entry in new_data_entries:
                 content.append(f"{entry}\n")

            # Add trailing newline if missing from last line
            if content and not content[-1].endswith('\n'):
                content[-1] += '\n'

            # Write back to file
            with open(project_file, 'w', encoding='utf-8') as f:
                f.writelines(content)

            self.status_label.setText(f"Project file {action} successfully!")
            self.status_label.setStyleSheet("color: #4CAF50;") # Green
            QMessageBox.information(
                self, "Success",
                f"Project file '{project_file.name}' {action} at:\n{project_file.parent}",
                QMessageBox.Ok
            )

        except Exception as e:
            self._handle_error("Error creating/updating project file", e)

    # Context menu is replaced by double-click
    # def show_context_menu(self, position):
    #     """Show context menu for table items (Plot Waveform)"""
    #     # Get the item at the clicked position
    #     item = self.table.itemAt(position)
    #     if not item: return

    #     row = item.row()
    #     if row < 0: return # No valid row selected

    #     # Get waveform file from the row (column 5 is Waveform File)
    #     waveform_item = self.table.item(row, 5)
    #     waveform_file = waveform_item.text() if waveform_item else None

    #     if waveform_file and waveform_file != 'N/A':
    #         menu = QMenu(self) # Parent the menu
    #         plot_action = menu.addAction("Plot/Edit Waveform")
    #         action = menu.exec_(self.table.viewport().mapToGlobal(position))

    #         if action == plot_action:
    #             try:
    #                 # Construct full path to waveform file
    #                 waveform_path = Path(self.file_data['root_dir']) / "Provus_Options" / "Waveforms" / waveform_file
    #                 if waveform_path.exists():
    #                     self.preview_waveform(str(waveform_path))
    #                 else:
    #                      raise FileNotFoundError(f"Waveform file not found: {waveform_path}")
    #             except Exception as e:
    #                 self._handle_error("Waveform Preview Error", e)


    def preview_waveform(self, waveform_path_str):
        """Launch the waveform editor/preview window"""
        try:
            # Handle both full path and filename-only cases
            waveform_path = Path(waveform_path_str)
            
            # If it's just a filename, construct the full path
            if not waveform_path.is_absolute():
                root_dir = self.file_data.get('root_dir')
                if not root_dir:
                    raise ValueError("Root directory not set")
                waveform_path = Path(root_dir) / "Provus_Options" / "Waveforms" / waveform_path_str
            
            if not waveform_path.exists():
                raise FileNotFoundError(f"Waveform file not found: {waveform_path}")

            # Import and run waveform generator module directly
            from core.waveform_generator import edit_waveform
            logger.info(f"Launching waveform editor for: {waveform_path}")
            
            # Store reference to window to prevent garbage collection
            editor_window = edit_waveform(str(waveform_path))
            if editor_window:
                # Store reference to prevent garbage collection
                self._waveform_windows.append(editor_window)
                # Set window to remain after closing the parent
                editor_window.setAttribute(Qt.WA_DeleteOnClose, True)

        except ImportError:
            self._handle_error("Waveform Preview Error", ModuleNotFoundError("Could not import the Waveform Editor module."))
        except FileNotFoundError as fnf:
             self._handle_error("Waveform Preview Error", fnf)
        except Exception as e:
            self._handle_error("Waveform Preview Error", e)


    def on_cell_double_clicked(self, row, column):
        """Handle double-click on table cells to preview waveform"""
        try:
            # Implement debounce to prevent multiple rapid clicks
            current_time = time.time()
            if current_time - self.last_double_click_time < 1.0:  # 1 second debounce
                logger.debug("Double-click debounced - ignoring rapid sequential clicks")
                return
            
            self.last_double_click_time = current_time
            
            if row < 0: return # Ignore header clicks

            # Get waveform file from the selected row (column 5 is Waveform File)
            waveform_item = self.table.item(row, 5)
            waveform_file = waveform_item.text() if waveform_item else None

            if waveform_file and waveform_file != 'N/A':
                # Pass just the filename to preview_waveform - it will handle path construction
                self.preview_waveform(waveform_file)
            else:
                logger.info(f"No valid waveform file assigned in row {row} to preview.")

        except Exception as e:
            self._handle_error("Error on Double Click", e)

# --- END OF FILE analysis.py ---