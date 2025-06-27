import os
import re
import logging
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton,
                            QMessageBox, QShortcut, QCheckBox, QComboBox, QGroupBox,
                            QInputDialog)
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis
from PyQt5.QtCore import Qt, QPointF, QTimer
from PyQt5.QtGui import QPen, QColor, QPainter, QDoubleValidator, QKeySequence, QIcon
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

class WaveformEditor(QMainWindow):
    def __init__(self, csv_path):
        super().__init__()
        self.csv_path = csv_path
        self.setWindowTitle("Waveform Editor")
        self.setGeometry(100, 100, 1000, 600)
        
        # Set window icon
        self.set_window_icon()
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        # Create left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Waveform name input
        name_widget = QWidget()
        name_layout = QHBoxLayout(name_widget)
        name_layout.addWidget(QLabel("Waveform Name:"))
        self.name_input = QLineEdit()
        name_layout.addWidget(self.name_input)
        left_layout.addWidget(name_widget)
        
        # Base frequency input with validation
        freq_widget = QWidget()
        freq_layout = QHBoxLayout(freq_widget)
        freq_layout.addWidget(QLabel("Base Frequency (Hz):"))
        self.freq_input = QLineEdit()
        
        # Add validator for frequency input
        freq_validator = QDoubleValidator()
        freq_validator.setBottom(0.1)  # Minimum frequency
        freq_validator.setTop(1000.0)  # Maximum frequency
        self.freq_input.setValidator(freq_validator)
        
        freq_layout.addWidget(self.freq_input)
        left_layout.addWidget(freq_widget)
        
        # Zero time input with validation
        zero_time_widget = QWidget()
        zero_time_layout = QHBoxLayout(zero_time_widget)
        zero_time_layout.addWidget(QLabel("Waveform Zero Time:"))
        self.zero_time_input = QLineEdit()
        
        # Add validator for zero time input
        zero_time_validator = QDoubleValidator()
        zero_time_validator.setBottom(0.0)  # Allow values >= 0
        self.zero_time_input.setValidator(zero_time_validator)
        self.zero_time_input.textChanged.connect(self.validate_zero_time)
        
        zero_time_layout.addWidget(self.zero_time_input)
        left_layout.addWidget(zero_time_widget)
        
        # Scaled time toggle
        self.scaled_time_checkbox = QCheckBox("Use Scaled Time (0-1)")
        self.scaled_time_checkbox.setChecked(True)  # Default to checked
        self.scaled_time_checkbox.toggled.connect(self.on_scaled_time_toggled)
        self.scaled_time_checkbox.setToolTip("When checked: time is scaled 0-1\nWhen unchecked: time is in milliseconds")
        left_layout.addWidget(self.scaled_time_checkbox)
        
        # Waveform shapes section
        shapes_group = QGroupBox("Waveform Shapes")
        shapes_layout = QVBoxLayout(shapes_group)
        
        self.shapes_combo = QComboBox()
        self.shapes_combo.addItem("Custom / Manual Entry")
        self.shapes_combo.addItem("Square Wave")
        self.shapes_combo.addItem("Half Sine")
        self.shapes_combo.addItem("Square with Offtime")
        self.shapes_combo.addItem("Triangle")
        
        generate_btn = QPushButton("Generate Selected Shape")
        generate_btn.clicked.connect(self.generate_waveform_shape)
        
        shapes_layout.addWidget(QLabel("Basic Waveform Shapes:"))
        shapes_layout.addWidget(self.shapes_combo)
        shapes_layout.addWidget(generate_btn)
        left_layout.addWidget(shapes_group)
        
        # Points editor with validation
        points_label = QLabel("Data Points (Time, Current)")
        self.points_status = QLabel("")  # Status label for points validation
        self.points_status.setStyleSheet("color: #666; font-size: 10px;")
        left_layout.addWidget(points_label)
        left_layout.addWidget(self.points_status)
        
        self.points_editor = QTextEdit()
        self.points_editor.textChanged.connect(self.validate_points)
        self.points_editor.setToolTip("Supports two formats:\nComma: time,current (0.0,1.0)\nSpace: time    current (0.0    1.0)")
        left_layout.addWidget(self.points_editor)
        
        # Buttons
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        
        update_button = QPushButton("Update Plot (F5)")
        update_button.clicked.connect(self.update_plot)
        
        save_exit_button = QPushButton("Save and Exit (Ctrl+S)")
        save_exit_button.clicked.connect(self.save_and_exit)
        
        close_button = QPushButton("Close (Esc)")
        close_button.clicked.connect(self.close)
        
        buttons_layout.addWidget(update_button)
        buttons_layout.addWidget(save_exit_button)
        buttons_layout.addWidget(close_button)
        left_layout.addWidget(buttons_widget)
        
        # Add left panel to main layout
        layout.addWidget(left_panel)
        
        # Create chart with improved appearance
        self.chart = QChart()
        self.chart.setTheme(QChart.ChartThemeLight)
        self.chart.setBackgroundVisible(True)
        self.chart.setBackgroundBrush(QColor(250, 250, 250))
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignTop)
        self.chart.setTitle("Waveform Preview")
        self.chart.setTitleFont(self.chart.titleFont())
        
        # Create axes with improved formatting
        self.axis_x = QValueAxis()
        self.axis_x.setTitleText("Scaled Time")
        self.axis_x.setRange(0, 1)
        self.axis_x.setTickCount(11)
        self.axis_x.setGridLineVisible(True)
        self.axis_x.setMinorTickCount(1)
        self.axis_x.setLabelFormat("%.2f")
        
        self.axis_y = QValueAxis()
        self.axis_y.setTitleText("Scaled Current")
        self.axis_y.setRange(-1.2, 1.2)
        self.axis_y.setTickCount(13)
        self.axis_y.setGridLineVisible(True)
        self.axis_y.setMinorTickCount(1)
        self.axis_y.setLabelFormat("%.2f")
        
        self.chart.addAxis(self.axis_x, Qt.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        
        # Create chart view
        chart_view = QChartView(self.chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        layout.addWidget(chart_view)
        
        # Set layout ratios
        layout.setStretch(0, 1)  # Left panel
        layout.setStretch(1, 2)  # Chart
        
        # Store original values for comparison
        self.original_zero_time = None
        self.original_points = None
        
        # Validation state
        self.zero_time_valid = True
        self.points_valid = True
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
        # Load data from CSV
        self.load_from_csv()
        self.update_plot()
    
    def set_window_icon(self):
        """Set the window icon using the same logic as main.py"""
        try:
            # Use same logic as main.py get_icon_path()
            if getattr(sys, 'frozen', False):
                # Running in PyInstaller bundle
                base_path = Path(sys._MEIPASS)
            else:
                # Running in development
                base_path = Path(os.path.dirname(os.path.abspath(__file__))).parent
            
            icon_path = base_path / "assets" / "icon.ico"
            if not icon_path.exists():
                icon_path = base_path / "provus_formatter" / "assets" / "icon.ico"
            
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                logger.debug(f"Set waveform editor icon from: {icon_path}")
            else:
                logger.warning(f"Icon not found at: {icon_path}")
                
        except Exception as e:
            logger.error(f"Error setting waveform editor icon: {str(e)}")
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts for common actions"""
        # F5 - Update plot
        update_shortcut = QShortcut(QKeySequence("F5"), self)
        update_shortcut.activated.connect(self.update_plot)
        
        # Ctrl+S - Save and exit
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_and_exit)
        
        # Escape - Close window
        close_shortcut = QShortcut(QKeySequence("Escape"), self)
        close_shortcut.activated.connect(self.close)
        
        # Ctrl+U - Focus zero time input
        focus_zero_shortcut = QShortcut(QKeySequence("Ctrl+U"), self)
        focus_zero_shortcut.activated.connect(lambda: self.zero_time_input.setFocus())
        
        # Ctrl+E - Focus points editor
        focus_points_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        focus_points_shortcut.activated.connect(lambda: self.points_editor.setFocus())
    
    def on_scaled_time_toggled(self):
        """Handle scaled time checkbox toggle"""
        is_scaled = self.scaled_time_checkbox.isChecked()
        
        # Update axis title based on scaled time setting
        if is_scaled:
            self.axis_x.setTitleText("Scaled Time")
            self.axis_x.setRange(0, 1)
            # Convert data points to scaled time if they appear to be in ms
            self.convert_to_scaled_time()
        else:
            self.axis_x.setTitleText("Time (ms)")
            # We'll update the range dynamically based on data
        
        # Update the plot with current data
        self.update_plot()
    
    def convert_to_scaled_time(self):
        """Convert data points to scaled time (0-0.5) if they appear to be in ms"""
        try:
            points_text = self.points_editor.toPlainText().strip()
            if not points_text:
                return
            
            # Parse current points to check if conversion is needed
            points = self.parse_points()
            if not points:
                return
            
            # Check if any time values are > 0.5 (indicating they're likely in ms)
            max_time = max(point[0] for point in points)
            if max_time <= 0.5:
                return  # Already in scaled time, no conversion needed
            
            # Convert points to scaled time (normalize to 0-0.5 range)
            converted_lines = []
            lines = points_text.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    converted_lines.append('')
                    continue
                
                # Skip header lines
                if any(keyword in line.lower() for keyword in ['time', 'amplitude', 'current', '(ms)', '(0-1)']):
                    # Update header to reflect scaled time
                    if '(ms)' in line:
                        line = line.replace('(ms)', '(scaled)')
                    converted_lines.append(line)
                    continue
                
                # Convert data lines
                time_val = None
                current_val = None
                
                # Try comma-delimited format
                if ',' in line:
                    try:
                        time_str, current_str = line.split(',', 1)
                        time_val = float(time_str.strip()) / max_time * 0.5  # Scale to 0-0.5
                        current_val = float(current_str.strip())
                        converted_lines.append(f"{time_val:.6f},{current_val}")
                        continue
                    except ValueError:
                        converted_lines.append(line)
                        continue
                
                # Try space-delimited format
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        time_val = float(parts[0]) / max_time * 0.5  # Scale to 0-0.5
                        current_val = float(parts[1])
                        # Maintain original spacing/formatting
                        spacing = ' ' * (16 - len(f"{time_val:.6f}"))  # Align to match original format
                        converted_lines.append(f"{time_val:.6f}{spacing}{current_val}")
                        continue
                    except ValueError:
                        converted_lines.append(line)
                        continue
                
                # If we can't parse it, keep the original line
                converted_lines.append(line)
            
            # Update the text editor with converted data
            self.points_editor.setPlainText('\n'.join(converted_lines))
            
        except Exception as e:
            print(f"Error converting to scaled time: {str(e)}")
    
    def generate_waveform_shape(self):
        """Generate the selected waveform shape"""
        try:
            shape = self.shapes_combo.currentText()
            
            if shape == "Custom / Manual Entry":
                QMessageBox.information(self, "Manual Entry", 
                                      "You are in manual entry mode. Enter data points manually.")
                return
            
            # Get number of points for smooth curves
            num_points = 50
            is_scaled = self.scaled_time_checkbox.isChecked()
            
            # Generate waveforms based on type
            points = []
            zero_time = 0.0  # Default
            
            if shape == "Square Wave":
                points, zero_time = self.generate_square_wave()
                
            elif shape == "Half Sine":
                points, zero_time = self.generate_half_sine()
                
            elif shape == "Square with Offtime":
                points, zero_time = self.generate_square_with_offtime()
                
            elif shape == "Triangle":
                points, zero_time = self.generate_triangle_wave()
            
            if points:
                # Format as text for the editor
                points_text = '\n'.join([f"{time:.6f},{current:.6f}" for time, current in points])
                self.points_editor.setPlainText(points_text)
                
                # Set appropriate zero time
                self.zero_time_input.setText(str(zero_time))
                
                # Update the plot
                self.update_plot()
                
                QMessageBox.information(self, "Shape Generated", 
                                      f"Generated {shape} with {len(points)} points")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generating waveform: {str(e)}")
    
    def generate_square_wave(self):
        """Generate square wave: 0.0000,-1.000000 -> 0.0001,1.000000 -> 0.5000,1.000000"""
        points = [
            (0.0000, -1.000000),
            (0.0001, 1.000000),
            (0.5000, 1.000000)
        ]
        zero_time = 0.0000
        return points, zero_time
    
    def generate_half_sine(self):
        """Generate half sine wave with user-specified pulse width and base frequency"""
        import math
        
        # Get base frequency from input field
        try:
            base_freq = float(self.freq_input.text()) if self.freq_input.text() else 2.0
        except ValueError:
            base_freq = 2.0  # Default fallback
        
        # Prompt user for pulse width
        pulse_width, ok = QInputDialog.getDouble(
            self, 
            "Half Sine Parameters", 
            f"Enter pulse width (ms) for {base_freq} Hz half sine wave:",
            64.0,  # Default value (64ms like your example)
            0.1,   # Minimum
            1000.0,  # Maximum
            1      # Decimals
        )
        
        if not ok:
            return [], 0.0  # User cancelled
        
        # Calculate pulse width in scaled time
        period_ms = 1000.0 / base_freq
        pulse_width_scaled = pulse_width / period_ms
        
        # Generate half sine wave points
        points = []
        num_points = 37  # Match your example (37 points before the final 0.5,0.0)
        
        # Generate sine wave over the pulse width
        for i in range(num_points):
            # Time from 0 to pulse_width_scaled
            t = (i / (num_points - 1)) * pulse_width_scaled
            # Sine from 0 to pi over the pulse width
            amplitude = math.sin(math.pi * i / (num_points - 1))
            points.append((t, amplitude))
        
        # Add final point at 0.5 scaled time with 0 amplitude
        points.append((0.500000, 0.0))
        
        zero_time = 0.0000
        return points, zero_time
    
    def generate_square_with_offtime(self):
        """Generate square wave with offtime: pulse until 0.25, then off until 0.5"""
        points = [
            (0.0000, 0.000000),
            (0.0001, 1.000000),
            (0.2500, 1.000000),
            (0.2501, 0.000000),
            (0.5000, 0.000000)
        ]
        zero_time = 0.25001
        return points, zero_time
    
    def generate_triangle_wave(self):
        """Generate triangle wave: 0.000000,1.0 -> 0.500000,-1.0"""
        points = [
            (0.000000, 1.0),
            (0.500000, -1.0)
        ]
        zero_time = 0.0000
        return points, zero_time
    
    def validate_zero_time(self):
        """Validate zero time input with visual feedback"""
        try:
            text = self.zero_time_input.text()
            if not text:
                self.zero_time_input.setStyleSheet("")
                self.zero_time_valid = True
                return
            
            value = float(text)
            if value >= 0:
                self.zero_time_input.setStyleSheet("QLineEdit { border: 2px solid #4CAF50; }")
                self.zero_time_valid = True
            else:
                self.zero_time_input.setStyleSheet("QLineEdit { border: 2px solid #f44336; }")
                self.zero_time_valid = False
        except ValueError:
            self.zero_time_input.setStyleSheet("QLineEdit { border: 2px solid #f44336; }")
            self.zero_time_valid = False
    
    def validate_points(self):
        """Validate data points with visual feedback and status"""
        try:
            points_text = self.points_editor.toPlainText().strip()
            if not points_text:
                self.points_status.setText("")
                self.points_editor.setStyleSheet("")
                self.points_valid = True
                return
            
            valid_points = 0
            invalid_lines = 0
            
            for line_num, line in enumerate(points_text.split('\n'), 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                
                # Skip header lines that might contain text
                if any(keyword in line.lower() for keyword in ['time', 'amplitude', 'current', '(ms)', '(0-1)']):
                    continue
                    
                # Try comma-delimited format first
                if ',' in line:
                    try:
                        time_str, current_str = line.split(',', 1)
                        float(time_str.strip())
                        float(current_str.strip())
                        valid_points += 1
                        continue
                    except ValueError:
                        invalid_lines += 1
                        continue
                
                # Try space-delimited format
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        float(parts[0])  # time
                        float(parts[1])  # current/amplitude
                        valid_points += 1
                        continue
                    except ValueError:
                        invalid_lines += 1
                        continue
                
                # If we get here, the line doesn't match either format
                invalid_lines += 1
            
            if invalid_lines == 0 and valid_points > 0:
                self.points_status.setText(f"✓ {valid_points} valid data points")
                self.points_status.setStyleSheet("color: #4CAF50; font-size: 10px;")
                self.points_editor.setStyleSheet("QTextEdit { border: 2px solid #4CAF50; }")
                self.points_valid = True
            elif invalid_lines > 0:
                self.points_status.setText(f"⚠ {valid_points} valid, {invalid_lines} invalid lines")
                self.points_status.setStyleSheet("color: #ff9800; font-size: 10px;")
                self.points_editor.setStyleSheet("QTextEdit { border: 2px solid #ff9800; }")
                self.points_valid = valid_points > 0
            else:
                self.points_status.setText("No valid data points found")
                self.points_status.setStyleSheet("color: #f44336; font-size: 10px;")
                self.points_editor.setStyleSheet("QTextEdit { border: 2px solid #f44336; }")
                self.points_valid = False
                
        except Exception as e:
            self.points_status.setText(f"Error validating points: {str(e)}")
            self.points_status.setStyleSheet("color: #f44336; font-size: 10px;")
            self.points_editor.setStyleSheet("QTextEdit { border: 2px solid #f44336; }")
            self.points_valid = False
        
    def load_from_csv(self):
        """Load data from CSV file"""
        try:
            with open(self.csv_path, 'r') as f:
                lines = f.readlines()
                
            # Parse header information
            for line in lines[:4]:  # First 4 lines are headers
                if 'Waveform Name' in line:
                    waveform_name = line.strip().split(',')[1]
                elif 'BaseFrequency' in line:
                    base_freq = line.strip().split(',')[1]
                elif 'Base Frequency' in line:
                    base_freq = line.strip().split(',')[1]
                elif 'Waveform Zero Time' in line:
                    zero_time = line.strip().split(',')[1]
            
            # Set header information (name read-only, frequency editable)
            self.name_input.setText(waveform_name)
            self.name_input.setReadOnly(True)
            self.freq_input.setText(base_freq)
            self.freq_input.setReadOnly(False)  # Make frequency editable
            self.zero_time_input.setText(zero_time)
            
            # Store original zero time
            self.original_zero_time = zero_time
            
            # Read time/current data points, skipping header rows
            points_data = []
            for line in lines[4:]:  # Skip headers
                if line.strip() and not line.startswith('Scaled Time'):  # Skip the column headers
                    points_data.append(line.strip())
            
            # Set points data
            self.points_editor.setPlainText('\n'.join(points_data))
            
            # Store original points
            self.original_points = '\n'.join(points_data)
            
            # Trigger initial validation after loading
            self.validate_zero_time()
            self.validate_points()
            
        except Exception as e:
            print(f"Error loading CSV: {str(e)}")
    
    def save_and_exit(self):
        """Save data to CSV only if changes were made to zero time or points"""
        try:
            # Validate inputs before saving
            if not self.zero_time_valid:
                QMessageBox.warning(self, "Invalid Input", 
                                  "Zero time must be a valid number ≥ 0")
                return
            
            if not self.points_valid:
                QMessageBox.warning(self, "Invalid Input", 
                                  "Please fix invalid data points before saving")
                return
            
            current_points = self.points_editor.toPlainText().strip()
            current_zero_time = self.zero_time_input.text()
            
            # Check if any changes were made
            if (current_zero_time != self.original_zero_time or 
                current_points != self.original_points):
                
                # Read existing file content
                with open(self.csv_path, 'r') as f:
                    lines = f.readlines()
                
                # Update only zero time and points if changed
                lines[2] = f"Waveform Zero Time,{current_zero_time}\n"
                
                # Keep headers (first 4 lines)
                new_content = lines[:4]
                
                # Add updated points
                new_content.extend(f"{line}\n" for line in current_points.split('\n'))
                
                # Write back to file
                with open(self.csv_path, 'w', newline='') as f:
                    f.writelines(new_content)
            
            self.close()
            
        except Exception as e:
            print(f"Error saving CSV: {str(e)}")
    
    def parse_points(self):
        """Parse points from text editor - supports both comma and space delimited formats"""
        try:
            points_text = self.points_editor.toPlainText().strip()
            points = []
            
            for line in points_text.split('\n'):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                
                # Skip header lines
                if any(keyword in line.lower() for keyword in ['time', 'amplitude', 'current', '(ms)', '(0-1)']):
                    continue
                
                time_val = None
                current_val = None
                
                # Try comma-delimited format first
                if ',' in line:
                    try:
                        time_str, current_str = line.split(',', 1)
                        time_val = float(time_str.strip())
                        current_val = float(current_str.strip())
                    except ValueError:
                        continue
                else:
                    # Try space-delimited format
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            time_val = float(parts[0])
                            current_val = float(parts[1])
                        except ValueError:
                            continue
                
                if time_val is not None and current_val is not None:
                    points.append((time_val, current_val))
            
            return sorted(points, key=lambda x: x[0])
        except Exception as e:
            print(f"Error parsing points: {str(e)}")
            return []
    
    def update_plot(self):
        """Update the plot with current data"""
        try:
            # Clear existing series
            self.chart.removeAllSeries()
            
            # Get points and create full cycle
            points = self.parse_points()
            if not points:
                return
                
            time_points, current_points = zip(*points)
            
            is_scaled = self.scaled_time_checkbox.isChecked()
            
            if is_scaled:
                # For scaled time, normalize to 0-1 if not already
                max_time = max(time_points)
                if max_time > 1.1:  # If time values seem to be in ms, scale them
                    time_points = tuple(t / max_time for t in time_points)
                
                # Create full cycle (antisymmetric) - pure Python replacement
                # First half: original points
                # Second half: time shifted by 0.5, current inverted
                full_time = list(time_points) + [t + 0.5 for t in time_points]
                full_current = list(current_points) + [-c for c in current_points]
                
                # Set axis range for scaled time
                self.axis_x.setRange(0, 1)
            else:
                # For unscaled time (ms), use the data as-is but create antisymmetric cycle
                max_time = max(time_points)
                full_time = list(time_points) + [t + max_time for t in time_points]
                full_current = list(current_points) + [-c for c in current_points]
                
                # Set axis range based on data
                self.axis_x.setRange(0, max(full_time) * 1.1)
            
            # Create waveform series
            waveform_series = QLineSeries()
            waveform_series.setName("Waveform")
            pen = QPen(QColor("#2962FF"))
            pen.setWidth(2)
            waveform_series.setPen(pen)
            
            for t, c in zip(full_time, full_current):
                waveform_series.append(QPointF(t, c))
            
            self.chart.addSeries(waveform_series)
            
            # Add zero time line if applicable
            try:
                zero_time = float(self.zero_time_input.text())
                if zero_time >= 0:
                    zero_series = QLineSeries()
                    zero_series.setName("Zero Time")
                    pen = QPen(QColor("#D50000"))
                    pen.setWidth(2)
                    pen.setStyle(Qt.DashLine)
                    zero_series.setPen(pen)
                    
                    # Adjust zero time based on scaling
                    if not is_scaled and points:
                        # For unscaled time, use zero_time as-is in ms
                        display_zero_time = zero_time
                    else:
                        # For scaled time, normalize zero time if needed
                        display_zero_time = zero_time
                        if max_time > 1.1 and zero_time > 1:  # Convert from ms to scaled
                            display_zero_time = zero_time / max_time
                    
                    zero_series.append(QPointF(display_zero_time, -1.2))
                    zero_series.append(QPointF(display_zero_time, 1.2))
                    self.chart.addSeries(zero_series)
            except ValueError:
                pass  # Skip zero time line if invalid
            
            # Attach axes to series
            for series in self.chart.series():
                series.attachAxis(self.axis_x)
                series.attachAxis(self.axis_y)
                
        except Exception as e:
            print(f"Error updating plot: {str(e)}")

def edit_waveform(csv_path):
    """
    Launch a standalone waveform editor window.
    
    Args:
        csv_path: Path to CSV file containing waveform data.
        
    Returns:
        The editor window if embedded in existing application, None otherwise.
    """
    import sys
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    
    # Check if there's an existing QApplication instance
    app = QApplication.instance()
    if app is None:
        # Create a new QApplication if none exists
        app = QApplication([])
        needs_exec = True
    else:
        needs_exec = False
        
    window = WaveformEditor(csv_path)
    window.setWindowFlags(window.windowFlags() | Qt.Window)  # Set as independent window
    window.setAttribute(Qt.WA_DeleteOnClose, False)  # Prevent auto-deletion when closed
    window.show()
    
    # Only call exec_ if we created a new QApplication
    if needs_exec:
        app.exec_()
        return None  # Return None when running standalone
    else:
        # Return window to allow caller to keep a reference
        return window

if __name__ == "__main__":
    # Example usage with proper error handling
    try:
        import sys
        if len(sys.argv) > 1:
            # Use the provided command line argument path
            csv_file = sys.argv[1]
        else:
            # Default path if no argument provided
            csv_file = "path/to/your/waveform.csv"
        edit_waveform(csv_file)
    except Exception as e:
        print(f"Error: {str(e)}") 