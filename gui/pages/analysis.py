from PyQt5.QtWidgets import (QWizardPage, QVBoxLayout, QPushButton, 
                            QTableWidget, QTableWidgetItem, QComboBox,
                            QHBoxLayout, QHeaderView, QFileDialog, QMessageBox,
                            QLabel, QWidget, QMenu)
import logging
from pathlib import Path
from core.file_processor import FileProcessor
from core.mcg_parser import parse_mcg_file
import re
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

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
        
        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(8)  # Reduced from 9 to 8 columns
        headers = ["Filename", "Base Frequency", "Units", "# of Channels", 
                   "Tx Waveform", "Waveform File", "Sampling File", 
                   "Data Style"]  # Removed Preview column
        self.table.setHorizontalHeaderLabels(headers)
        
        # Connect context menu event
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
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
        
        # Remove context menu setup and replace with double-click handler
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
    def initializePage(self):
        """Called when page is shown"""
        self.process_files()
        self.update_table()
        self.update_dropdowns()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Add status label at top
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        # Create table with additional columns
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Filename", "Base Frequency", "Units", "# of Channels",
            "Tx Waveform", "Waveform File", "Sampling File",
            "Data Style"
        ])
        
        # Make the entire table read-only
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)
        
        # Dropdown container
        dropdown_layout = QHBoxLayout()
        
        # Add labels and dropdowns
        waveform_label = QLabel("Waveform File:")
        sampling_label = QLabel("Sampling File:")
        data_style_label = QLabel("Data Style:")  # Add new label
        
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
            
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
            
        # Get the first selected row's values
        row = self.table.row(selected_items[0])
        waveform_file = self.table.item(row, 5).text()
        sampling_file = self.table.item(row, 6).text()
        data_style = self.table.item(row, 7).text()  # Updated index
        
        # Temporarily disable dropdown signals
        self.ignore_selection_change = True
        
        # Update dropdowns without triggering their change events
        self.waveform_combo.blockSignals(True)
        self.sampling_combo.blockSignals(True)
        self.data_style_combo.blockSignals(True)
        
        self.waveform_combo.setCurrentText(waveform_file)
        self.sampling_combo.setCurrentText(sampling_file)
        self.data_style_combo.setCurrentText(data_style)
        
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
                return
            
            sender = self.sender()
            column = -1
            
            if sender == self.waveform_combo:
                column = 5
            elif sender == self.sampling_combo:
                column = 6
            elif sender == self.data_style_combo:
                column = 7
            
            if column != -1:
                for row in selected_rows:
                    self.table.setItem(row, column, QTableWidgetItem(value))
                    
                    # Update results dictionary with new value
                    file_path = self.table.item(row, 0).data(Qt.UserRole)
                    if file_path in self.results:
                        if column == 5:  # Waveform file changed
                            self.results[file_path]['waveform_file'] = value
                        elif column == 6:  # Sampling file changed
                            self.results[file_path]['sampling_file'] = value
                        elif column == 7:  # Data Style changed
                            # No need to store data style in results as it's derived from tx_waveform
                            pass
        except Exception as e:
            logger.error(f"Error handling dropdown change: {str(e)}", exc_info=True)

    def import_from_mcg(self):
        """Import waveform and sampling files from MCG"""
        try:
            # Get MCG file from user
            mcg_file, _ = QFileDialog.getOpenFileName(
                self, "Select MCG File", "", "MCG Files (*.mcg)"
            )
            
            if mcg_file:
                # Set ignore flag before processing
                self.ignore_selection_change = True
                
                # Process MCG file
                parse_mcg_file(mcg_file, self.file_data['root_dir'])
                
                # Store current selections before updating dropdowns
                current_waveform = self.waveform_combo.currentText()
                current_sampling = self.sampling_combo.currentText()
                
                # Update dropdown menus
                self.update_dropdowns()
                
                # Restore previous selections
                waveform_index = self.waveform_combo.findText(current_waveform)
                sampling_index = self.sampling_combo.findText(current_sampling)
                
                if waveform_index >= 0:
                    self.waveform_combo.setCurrentIndex(waveform_index)
                if sampling_index >= 0:
                    self.sampling_combo.setCurrentIndex(sampling_index)
                
                # Reset ignore flag
                self.ignore_selection_change = False
                
                # Show success message
                mcg_name = Path(mcg_file).name
                QMessageBox.information(
                    self,
                    "Import Successful",
                    f"CSV files successfully created from {mcg_name}",
                    QMessageBox.Ok
                )
                
        except Exception as e:
            self.ignore_selection_change = False
            logger.error(f"Error importing MCG file: {str(e)}", exc_info=True)
            QMessageBox.critical(
                self,
                "Import Error",
                f"Error importing MCG file:\n{str(e)}",
                QMessageBox.Ok
            )

    def process_files(self):
        """Process all files and store results"""
        try:
            if not self.file_data['root_dir']:
                return
                
            processor = FileProcessor(self.file_data['root_dir'])
            
            # Create output directories
            waveform_dir = Path(self.file_data['root_dir']) / "Provus_Options" / "Waveforms"
            sampling_dir = Path(self.file_data['root_dir']) / "Provus_Options" / "Channel_Sampling_Schemes"
            waveform_dir.mkdir(parents=True, exist_ok=True)
            sampling_dir.mkdir(parents=True, exist_ok=True)
            
            for file_path in self.file_data['tem_files']:
                path = Path(file_path)
                if path.suffix.lower() == '.tem':
                    # Process TEM files
                    header_data = processor.parse_file_headers(file_path)
                    if header_data:
                        # Generate waveform file
                        waveform_file = processor._generate_waveform_csv(header_data, waveform_dir)
                        if waveform_file:
                            # Generate sampling file
                            sampling_file = processor._generate_sampling_csv(header_data, waveform_file, sampling_dir)
                            
                            # Store results
                            self.results[file_path] = {
                                'base_frequency': header_data.get('base_frequency', 'N/A'),
                                'units': header_data.get('units', 'N/A'),
                                'num_channels': header_data.get('num_channels', 'N/A'),
                                'tx_waveform': header_data.get('tx_waveform', 'Undefined'),
                                'waveform_file': waveform_file,
                                'sampling_file': sampling_file
                            }
                        
                elif path.suffix.lower() == '.pem':
                    # Process PEM files
                    try:
                        base_freq, ramp_time, survey_params, time_windows = processor.parse_pem_file(file_path)
                        
                        base_name = path.stem
                        waveform_file = f"Crone_{base_freq:.0f}Hz.csv"
                        sampling_file = f"Crone_{base_freq:.0f}Hz_{len(time_windows)-3}ch.csv"
                        
                        processor.generate_pem_waveform_csv(base_name, base_freq, ramp_time, 
                                                          waveform_dir / waveform_file)
                        processor.generate_pem_sampling_csv(base_name, time_windows, 
                                                          sampling_dir / sampling_file)
                        
                        # Store results for display
                        self.results[file_path] = {
                            'base_frequency': f"{base_freq:.1f}",
                            'units': survey_params['units'],
                            'num_channels': len(time_windows) - 3,
                            'tx_waveform': 'Crone',
                            'waveform_file': waveform_file,
                            'sampling_file': sampling_file
                        }
                        
                    except Exception as e:
                        logger.error(f"Error processing PEM file {path.name}: {str(e)}")
                        self.results[file_path] = None
                        
            self.update_table()
            
        except Exception as e:
            self._handle_error("Error processing files", e)

    def _handle_error(self, message, error):
        """Centralized error handling"""
        logger.error(f"{message}: {str(error)}", exc_info=True)
        self.status_label.setText(f"{message}!")
        self.status_label.setStyleSheet("color: #f44336;")
        
        error_msg = QMessageBox()
        error_msg.setIcon(QMessageBox.Critical)
        error_msg.setText(message)
        error_msg.setInformativeText(str(error))
        error_msg.setWindowTitle("Error")
        error_msg.exec_()

    def update_table(self):
        """Update table with current results"""
        try:
            self.table.setRowCount(len(self.results))
            
            for row, (file_path, result_data) in enumerate(self.results.items()):
                if result_data is None:
                    continue
                    
                filename = Path(file_path).name
                
                # Create items
                filename_item = QTableWidgetItem(filename)
                filename_item.setData(Qt.UserRole, file_path)
                
                freq_item = QTableWidgetItem(str(result_data.get('base_frequency', 'N/A')))
                freq_item.setFlags(freq_item.flags() & ~Qt.ItemIsEditable)
                
                units_item = QTableWidgetItem(str(result_data.get('units', 'N/A')))
                units_item.setFlags(units_item.flags() & ~Qt.ItemIsEditable)
                
                channels_item = QTableWidgetItem(str(result_data.get('num_channels', 'N/A')))
                channels_item.setFlags(channels_item.flags() & ~Qt.ItemIsEditable)
                
                tx_waveform_item = QTableWidgetItem(str(result_data.get('tx_waveform', 'Undefined')))
                tx_waveform_item.setFlags(tx_waveform_item.flags() & ~Qt.ItemIsEditable)
                
                waveform_item = QTableWidgetItem(str(result_data.get('waveform_file', 'N/A')))
                waveform_item.setFlags(waveform_item.flags() & ~Qt.ItemIsEditable)
                
                sampling_item = QTableWidgetItem(str(result_data.get('sampling_file', 'N/A')))
                sampling_item.setFlags(sampling_item.flags() & ~Qt.ItemIsEditable)
                
                # Determine Data Style based on tx_waveform
                tx_waveform = result_data.get('tx_waveform', '')
                if tx_waveform == 'UTEM':
                    data_style = "DataFileStyleBoreholeUTEM"
                elif tx_waveform == 'Crone':
                    data_style = "DataFileStyleCrone"
                else:
                    data_style = "DataFileStyleBoreholeSJV"
                
                data_style_item = QTableWidgetItem(data_style)
                data_style_item.setFlags(data_style_item.flags() & ~Qt.ItemIsEditable)
                
                # Set items in table
                self.table.setItem(row, 0, filename_item)
                self.table.setItem(row, 1, freq_item)
                self.table.setItem(row, 2, units_item)
                self.table.setItem(row, 3, channels_item)
                self.table.setItem(row, 4, tx_waveform_item)
                self.table.setItem(row, 5, waveform_item)
                self.table.setItem(row, 6, sampling_item)
                self.table.setItem(row, 7, data_style_item)
            
            # Update comboboxes
            self.update_dropdowns()
            
            # Resize columns to content
            self.table.resizeColumnsToContents()
            
        except Exception as e:
            logger.error(f"Error updating table: {str(e)}", exc_info=True)
    
    def update_dropdowns(self):
        """Update dropdown menus with available options"""
        try:
            # Clear existing items
            self.waveform_combo.clear()
            self.sampling_combo.clear()
            
            # Get files from directories
            waveform_dir = Path(self.file_data['root_dir']) / "Provus_Options" / "Waveforms"
            sampling_dir = Path(self.file_data['root_dir']) / "Provus_Options" / "Channel_Sampling_Schemes"
            
            # Add files to dropdowns if directories exist
            if waveform_dir.exists():
                waveform_files = sorted([f.name for f in waveform_dir.glob('*.csv')])
                self.waveform_combo.addItems(waveform_files)
            
            if sampling_dir.exists():
                sampling_files = sorted([f.name for f in sampling_dir.glob('*.csv')])
                self.sampling_combo.addItems(sampling_files)
            
        except Exception as e:
            logger.error(f"Error updating dropdowns: {str(e)}", exc_info=True)
    
    def write_headers(self):
        """Write headers to data files"""
        try:
            self.status_label.setText("Updating headers...")
            self.status_label.setStyleSheet("color: #1976D2;")
            
            # Create FileProcessor instance
            file_processor = FileProcessor(self.file_data['root_dir'])
            
            total_files = len(self.results)
            processed = 0
            
            for row in range(self.table.rowCount()):
                # Get the full file path and check if it's a TEM file
                file_path = self.table.item(row, 0).data(Qt.UserRole)
                if not file_path.lower().endswith('.tem'):
                    continue  # Skip PEM files
                
                waveform_file = self.table.item(row, 5).text()
                sampling_file = self.table.item(row, 6).text()
                
                # Get waveform name without .csv extension
                waveform_name = Path(waveform_file).stem
                sampling_name = Path(sampling_file).stem
                
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                
                # Find and modify the frequency line
                for i, line in enumerate(lines):
                    if any(pattern in line for pattern in ['BFREQ', 'BASEFREQ', 'BASEFREQUENCY']):
                        base_line = line.rstrip()
                        ends_with_amp = base_line.endswith('&')
                        base_line = base_line.rstrip('&').rstrip()
                        
                        # Remove any existing WAVEFORM and SAMPLING entries
                        base_parts = base_line.split('\t')
                        cleaned_parts = [p for p in base_parts if not (p.startswith('WAVEFORM:') or p.startswith('SAMPLING:'))]
                        
                        # Add waveform and sampling info without .csv extension
                        cleaned_parts.extend([
                            f"WAVEFORM: {waveform_name}",
                            f"SAMPLING: {sampling_name}"
                        ])
                        
                        # Reconstruct the line
                        new_line = '\t'.join(cleaned_parts)
                        if ends_with_amp:
                            new_line += " &"
                        new_line += "\n"
                        
                        lines[i] = new_line
                        break
                
                # Write modified content back to file
                with open(file_path, 'w') as f:
                    f.writelines(lines)
                
                processed += 1
                self.status_label.setText(f"Updating headers... ({processed}/{total_files})")
            
            self.status_label.setText("Headers updated successfully!")
            self.status_label.setStyleSheet("color: #4CAF50;")
            
            QMessageBox.information(
                self,
                "Success",
                f"Successfully updated headers in {total_files} files",
                QMessageBox.Ok
            )
            
        except Exception as e:
            self._handle_error("Error updating headers", e)

    def create_project_file(self):
        """Create or update project file"""
        try:
            self.status_label.setText("Creating project file...")
            self.status_label.setStyleSheet("color: #1976D2;")
            
            root_path = Path(self.file_data['root_dir'])
            
            # Look for existing .ppf files
            existing_ppf = list(root_path.glob('*.ppf'))
            if existing_ppf:
                project_file = existing_ppf[0]  # Use the first found .ppf file
                logger.info(f"Found existing project file: {project_file}")
            else:
                project_file = root_path / "project.ppf"
                logger.info("No existing project file found, creating new one")
            
            # Prepare new entries
            new_entries = []
            for row in range(self.table.rowCount()):
                file_path = Path(self.table.item(row, 0).data(Qt.UserRole))
                data_style = self.table.item(row, 7).text()
                
                # Get relative path
                rel_path = file_path.relative_to(root_path)
                new_entries.append(f"{rel_path},{data_style}")
            
            if project_file.exists():
                # Read existing content
                with open(project_file, 'r') as f:
                    content = f.readlines()
                
                # Find where to insert new entries
                data_files_index = -1
                for i, line in enumerate(content):
                    if '[Project Data Files]' in line:
                        data_files_index = i
                        break
                
                if data_files_index == -1:
                    # Section not found, append it
                    content.extend(['\n[Project Data Files]\n'])
                    data_files_index = len(content) - 1
                
                # Ensure there's a newline after the section header
                if not content[data_files_index].endswith('\n'):
                    content[data_files_index] += '\n'
                
                # Remove any existing entries after the section header
                content = content[:data_files_index + 1]
                
                # Insert new entries after the section header
                for entry in new_entries:
                    content.append(f"{entry}\n")
                
                # Write back to file
                with open(project_file, 'w') as f:
                    f.writelines(content)
            else:
                # Create new file with proper formatting
                with open(project_file, 'w') as f:
                    f.write('[Project Settings]\n')
                    f.write('Project Name="Default"\n')
                    f.write('\n[Project Data Files]\n')  # Add blank line before section
                    for entry in new_entries:
                        f.write(f"{entry}\n")
            
            self.status_label.setText("Project file created successfully!")
            self.status_label.setStyleSheet("color: #4CAF50;")
            
            QMessageBox.information(
                self,
                "Success",
                f"Project file {'updated' if project_file.exists() else 'created'} at:\n{project_file}",
                QMessageBox.Ok
            )
            
        except Exception as e:
            self._handle_error("Error creating project file", e)

    def show_context_menu(self, position):
        """Show context menu for table items"""
        # Get the item at the clicked position
        item = self.table.itemAt(position)
        if not item:
            return
            
        row = item.row()
        
        # Get waveform file from the row (column 5 is Waveform File)
        waveform_file = self.table.item(row, 5).text()
        if waveform_file:
            menu = QMenu()
            plot_action = menu.addAction("Plot and Edit Waveform")
            
            # Show menu and get selected action
            action = menu.exec_(self.table.viewport().mapToGlobal(position))
            
            if action == plot_action:
                # Construct full path to waveform file
                waveform_path = Path(self.file_data['root_dir']) / "Provus_Options" / "Waveforms" / waveform_file
                self.preview_waveform(str(waveform_path))

    def preview_waveform(self, waveform_path):
        """Preview waveform for the given path"""
        try:
            if Path(waveform_path).exists():
                # Import and run waveform generator module directly
                from core.waveform_generator import edit_waveform
                # Store reference to window to prevent garbage collection
                self._waveform_window = edit_waveform(waveform_path)
            else:
                raise FileNotFoundError(f"Waveform file not found: {waveform_path}")
            
        except Exception as e:
            logger.error(f"Error previewing waveform: {str(e)}", exc_info=True)
            error_msg = QMessageBox()
            error_msg.setIcon(QMessageBox.Critical)
            error_msg.setText("Preview Error")
            error_msg.setInformativeText(str(e))
            error_msg.setWindowTitle("Error")
            error_msg.exec_()

    def create_data_style_combo(self):
        """Create combo box for Data Style selection"""
        combo = QComboBox()
        styles = [
            "DataFileStyleBoreholeUTEM",
            "DataFileStyleBoreholeSJV",
            "DataFileStyleCrone",
            "DataFileStyleSEM",
            "DataFileStyleDigiAtlantis"
        ]
        combo.addItems(styles)
        return combo

    def on_cell_double_clicked(self, row, column):
        """Handle double-click on table cells"""
        try:
            # Get waveform file from the row (column 5 is Waveform File)
            waveform_file = self.table.item(row, 5).text()
            if waveform_file:
                # Construct full path to waveform file
                waveform_path = Path(self.file_data['root_dir']) / "Provus_Options" / "Waveforms" / waveform_file
                self.preview_waveform(str(waveform_path))
            
        except Exception as e:
            logger.error(f"Error handling double-click: {str(e)}", exc_info=True)
            error_msg = QMessageBox()
            error_msg.setIcon(QMessageBox.Critical)
            error_msg.setText("Preview Error")
            error_msg.setInformativeText(str(e))
            error_msg.setWindowTitle("Error")
            error_msg.exec_() 