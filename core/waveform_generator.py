import numpy as np
import pandas as pd
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton,
                            QMessageBox)
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QColor, QPainter

class WaveformEditor(QMainWindow):
    def __init__(self, csv_path):
        super().__init__()
        self.csv_path = csv_path
        self.setWindowTitle("Waveform Editor")
        self.setGeometry(100, 100, 1000, 600)
        
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
        
        # Base frequency input
        freq_widget = QWidget()
        freq_layout = QHBoxLayout(freq_widget)
        freq_layout.addWidget(QLabel("Base Frequency:"))
        self.freq_input = QLineEdit()
        freq_layout.addWidget(self.freq_input)
        left_layout.addWidget(freq_widget)
        
        # Zero time input
        zero_time_widget = QWidget()
        zero_time_layout = QHBoxLayout(zero_time_widget)
        zero_time_layout.addWidget(QLabel("Waveform Zero Time:"))
        self.zero_time_input = QLineEdit()
        zero_time_layout.addWidget(self.zero_time_input)
        left_layout.addWidget(zero_time_widget)
        
        # Points editor
        left_layout.addWidget(QLabel("Data Points (Time, Current)"))
        self.points_editor = QTextEdit()
        left_layout.addWidget(self.points_editor)
        
        # Buttons
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        
        update_button = QPushButton("Update Plot")
        update_button.clicked.connect(self.update_plot)
        
        save_exit_button = QPushButton("Save and Exit")
        save_exit_button.clicked.connect(self.save_and_exit)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        
        buttons_layout.addWidget(update_button)
        buttons_layout.addWidget(save_exit_button)
        buttons_layout.addWidget(close_button)
        left_layout.addWidget(buttons_widget)
        
        # Add left panel to main layout
        layout.addWidget(left_panel)
        
        # Create chart
        self.chart = QChart()
        self.chart.setTheme(QChart.ChartThemeLight)
        self.chart.setBackgroundVisible(False)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignTop)
        
        # Create axes
        self.axis_x = QValueAxis()
        self.axis_x.setTitleText("Scaled Time")
        self.axis_x.setRange(0, 1)
        self.axis_x.setTickCount(11)
        
        self.axis_y = QValueAxis()
        self.axis_y.setTitleText("Scaled Current")
        self.axis_y.setRange(-1.2, 1.2)
        self.axis_y.setTickCount(13)
        
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
        
        # Load data from CSV
        self.load_from_csv()
        self.update_plot()
        
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
            
            # Set header information (read-only for name and frequency)
            self.name_input.setText(waveform_name)
            self.name_input.setReadOnly(True)
            self.freq_input.setText(base_freq)
            self.freq_input.setReadOnly(True)
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
            
        except Exception as e:
            print(f"Error loading CSV: {str(e)}")
    
    def save_and_exit(self):
        """Save data to CSV only if changes were made to zero time or points"""
        try:
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
        """Parse points from text editor"""
        try:
            points_text = self.points_editor.toPlainText().strip()
            points = []
            for line in points_text.split('\n'):
                if line.strip() and ',' in line:  # Make sure line has comma and isn't empty
                    try:
                        time, current = line.strip().split(',')
                        # Convert to float and add to points
                        points.append((float(time), float(current)))
                    except ValueError:
                        # Skip lines that can't be converted to float (like headers)
                        continue
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
            time_points, current_points = zip(*points)
            
            # Create full cycle (antisymmetric)
            full_time = np.concatenate([time_points, np.array(time_points) + 0.5])
            full_current = np.concatenate([current_points, -np.array(current_points)])
            
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
            zero_time = float(self.zero_time_input.text())
            if zero_time > 0 or zero_time == 0:
                zero_series = QLineSeries()
                zero_series.setName("Zero Time")
                pen = QPen(QColor("#D50000"))
                pen.setWidth(2)
                pen.setStyle(Qt.DashLine)
                zero_series.setPen(pen)
                zero_series.append(QPointF(zero_time, -1.2))
                zero_series.append(QPointF(zero_time, 1.2))
                self.chart.addSeries(zero_series)
            
            # Attach axes to series
            for series in self.chart.series():
                series.attachAxis(self.axis_x)
                series.attachAxis(self.axis_y)
                
        except Exception as e:
            print(f"Error updating plot: {str(e)}")

def edit_waveform(csv_path):
    """Main function to edit waveform from CSV file"""
    # Check if QApplication already exists
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        needs_exec = True
    else:
        needs_exec = False
        
    window = WaveformEditor(csv_path)
    window.show()
    
    # Only call exec_ if we created a new QApplication
    if needs_exec:
        app.exec_()
    else:
        # Keep a reference to the window to prevent it from being garbage collected
        window.setAttribute(Qt.WA_DeleteOnClose, False)
        return window  # Return window to prevent garbage collection

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