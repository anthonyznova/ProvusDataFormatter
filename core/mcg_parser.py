import re
import os
import csv
import math
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TimeCurrentPair:
    time: float
    current: float

@dataclass
class TEMHeader:
    base_frequency: float = 0.0
    units: str = ""
    duty_cycle: str = ""
    tx_waveform: str = ""
    system_info: str = ""
    survey_config: str = ""
    data_type: str = ""
    off_time: str = ""
    on_time: str = ""
    line: str = ""
    loop: str = ""
    project: str = ""
    client: str = ""
    current: float = 0.0
    bfield: str = ""
    instrument: str = ""
    configuration: str = ""
    receiver: str = ""
    times_start: List[float] = None
    times_end: List[float] = None
    times_center: List[float] = None
    times_width: List[float] = None
    time_units_original: str = ""
    time_units_applied: str = "ms"
    
    def __post_init__(self):
        if self.times_start is None:
            self.times_start = []
        if self.times_end is None:
            self.times_end = []
        if self.times_center is None:
            self.times_center = []
        if self.times_width is None:
            self.times_width = []

@dataclass  
class MCGHeader:
    base_frequency: float = 0.0
    on_time: float = 0.0
    off_time: float = 0.0
    turn_off_time: float = 0.0
    timing_mark: float = 0.0
    waveform_type: int = 0
    waveform_name: str = ""
    transmitter_name: str = ""
    receiver_name: str = ""
    configuration: int = 0
    units: int = 0
    num_channels: int = 0
    time_domain: bool = True
    bfield_response: bool = False
    channel_starts: List[float] = None
    channel_ends: List[float] = None
    waveform_points: List[TimeCurrentPair] = None
    
    def __post_init__(self):
        if self.channel_starts is None:
            self.channel_starts = []
        if self.channel_ends is None:
            self.channel_ends = []
        if self.waveform_points is None:
            self.waveform_points = []

class TEMParser:
    def __init__(self):
        self.header_patterns = {
            'base_frequency': re.compile(r'(?i)(?:BFREQ|BASEFREQ|BASEFREQUENCY)\s*[:=]\s*([\d.]+)'),
            'units': re.compile(r'(?i)UNITS\s*[:=]\s*(\S+)'),
            'duty_cycle': re.compile(r'(?i)(?:DUTYCYCLE|DUTY)\s*[:=]\s*(\S+)'),
            'tx_waveform': re.compile(r'(?i)(?:TXWAVEFORM|WAVEFORM)\s*[:=]\s*(\S+)'),
            'system_info': re.compile(r'(?i)(?:INSTRUMENT|SYSTEM|PRIMARYREMOVED)\s*[:=]\s*(\S+)'),
            'survey_config': re.compile(r'(?i)(?:CONFIG|CONFIGURATION)\s*[:=]\s*(\S+)'),
            'data_type': re.compile(r'(?i)DATATYPE\s*[:=]\s*(\S+)'),
            'off_time': re.compile(r'(?i)OFFTIME\s*[:=]\s*(\S+)'),
            'on_time': re.compile(r'(?i)ONTIME\s*[:=]\s*(\S+)'),
            'line': re.compile(r'(?i)LINE\s*[:=]\s*(\S+)'),
            'loop': re.compile(r'(?i)LOOP\s*[:=]\s*(\S+)'),
            'project': re.compile(r'(?i)PROJECT\s*[:=]\s*(\S+)'),
            'client': re.compile(r'(?i)CLIENT\s*[:=]\s*(\S+)'),
            'current': re.compile(r'(?i)CURRENT\s*[:=]\s*([\d.]+)'),
            'bfield': re.compile(r'(?i)BFIELD\s*[:=]\s*(\S+)'),
            'instrument': re.compile(r'(?i)INSTRUMENT\s*[:=]\s*(\S+)'),
            'receiver': re.compile(r'(?i)RECEIVER\s*[:=]\s*(\S+)')
        }
        
        self.time_patterns = {
            'times_start': re.compile(r'(?i)/?TIMESSTART\s*\(([^)]*)\)\s*[=:\s]+([\d.,\s]+)'),
            'times_end': re.compile(r'(?i)/?TIMESEND\s*\(([^)]*)\)\s*[=:\s]+([\d.,\s]+)'),
            'times_center': re.compile(r'(?i)/?TIMES\s*\(([^)]*)\)\s*[=:\s]+([\d.,\s]+)'),
            'times_width': re.compile(r'(?i)/?TIMESWIDTH\s*\(([^)]*)\)\s*[=:\s]+([\d.,\s]+)')
        }
    
    def parse_file(self, file_path: str) -> TEMHeader:
        """Parse TEM file and return header data"""
        header = TEMHeader()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    self._parse_header_line(line, header)
                    self._parse_time_window_line(line, header)
            
            self._normalize_time_units(header)
            self._convert_center_width_to_start_end(header)
            
        except Exception as e:
            logger.error(f"Error parsing TEM file {file_path}: {e}")
            raise
        
        return header
    
    def _parse_header_line(self, line: str, header: TEMHeader):
        """Parse header constants from a line"""
        for field, pattern in self.header_patterns.items():
            match = pattern.search(line)
            if match:
                value = match.group(1)
                if field in ['base_frequency', 'current']:
                    try:
                        setattr(header, field, float(value))
                    except ValueError:
                        logger.warning(f"Invalid numeric value for {field}: {value}")
                else:
                    setattr(header, field, value)
    
    def _parse_time_window_line(self, line: str, header: TEMHeader):
        """Parse time window data from a line"""
        for field, pattern in self.time_patterns.items():
            match = pattern.search(line)
            if match and len(match.groups()) >= 2:
                # Skip if this is actually TIMESSTART/TIMESEND/TIMESWIDTH when looking for TIMES
                if field == 'times_center':
                    line_upper = line.upper()
                    if any(x in line_upper for x in ['TIMESSTART', 'TIMESEND', 'TIMESWIDTH']):
                        continue
                
                units = match.group(1).strip()
                values_str = match.group(2)
                
                if not header.time_units_original and units:
                    header.time_units_original = units
                
                values = self._parse_float_array(values_str)
                setattr(header, field, values)
    
    def _parse_float_array(self, values_str: str) -> List[float]:
        """Parse comma-separated float values"""
        result = []
        parts = values_str.split(',')
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            try:
                result.append(float(part))
            except ValueError:
                logger.warning(f"Could not parse float value: {part}")
        
        return result
    
    def _normalize_time_units(self, header: TEMHeader):
        """Convert all time values to milliseconds"""
        if not header.time_units_original:
            return
        
        factor = self._get_time_conversion_factor(header.time_units_original)
        if factor == 1.0:
            return
        
        header.times_start = [t * factor for t in header.times_start]
        header.times_end = [t * factor for t in header.times_end]
        header.times_center = [t * factor for t in header.times_center]
        header.times_width = [t * factor for t in header.times_width]
    
    def _get_time_conversion_factor(self, unit: str) -> float:
        """Get conversion factor to milliseconds"""
        unit = unit.lower().strip()
        
        conversion_map = {
            'ms': 1.0, 'msec': 1.0, 'milliseconds': 1.0, 'millisecond': 1.0,
            's': 1000.0, 'sec': 1000.0, 'seconds': 1000.0, 'second': 1000.0,
            'us': 0.001, 'μs': 0.001, 'usec': 0.001, 'microseconds': 0.001, 'microsecond': 0.001,
            'ns': 0.000001, 'nsec': 0.000001, 'nanoseconds': 0.000001, 'nanosecond': 0.000001,
            'min': 60000.0, 'minutes': 60000.0, 'minute': 60000.0,
            'h': 3600000.0, 'hr': 3600000.0, 'hours': 3600000.0, 'hour': 3600000.0
        }
        
        return conversion_map.get(unit, 1.0)
    
    def _convert_center_width_to_start_end(self, header: TEMHeader):
        """Convert center/width format to start/end format"""
        if not header.times_center or not header.times_width:
            return
        if header.times_start or header.times_end:
            return  # Already have start/end data
        
        min_len = min(len(header.times_center), len(header.times_width))
        valid_centers = []
        valid_widths = []
        
        for i in range(min_len):
            center = header.times_center[i]
            width = header.times_width[i]
            
            if center > 0 and width > 0 and center < 1e6 and width < 1e6:
                valid_centers.append(center)
                valid_widths.append(width)
        
        if not valid_centers:
            return
        
        header.times_start = []
        header.times_end = []
        
        for center, width in zip(valid_centers, valid_widths):
            half_width = width / 2.0
            header.times_start.append(center - half_width)
            header.times_end.append(center + half_width)
        
        header.times_center = valid_centers
        header.times_width = valid_widths

class MCGParser:
    def __init__(self):
        self.key_value_pattern = re.compile(r'^\s*([^:]+?)\s*:\s*(.+?)$')
        self.channel_time_pattern = re.compile(r'^\s*(\d+)\s+([\d.]+)\s+([\d.]+)\s*$')
        self.waveform_point_pattern = re.compile(r'^\s*(\d+)\s+([\d.\-e]+)\s+([\d.\-e]+)\s*$')
    
    def parse_file(self, file_path: str) -> MCGHeader:
        """Parse MCG file and return header data"""
        header = MCGHeader()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                in_channel_times = False
                in_waveform_points = False
                
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('----'):
                        continue
                    
                    # Check section markers
                    if 'START OF CHANNEL TIMES' in line:
                        in_channel_times = True
                        continue
                    elif 'END OF CHANNEL TIMES' in line:
                        in_channel_times = False
                        continue
                    elif 'START OF STANDARD WAVEFORM' in line:
                        in_waveform_points = True
                        continue
                    elif 'END OF STANDARD WAVEFORM' in line:
                        in_waveform_points = False
                        continue
                    
                    # Skip column headers
                    if 'Ch  Start Time' in line or 'Pt  Time' in line:
                        continue
                    
                    if in_channel_times:
                        self._parse_channel_time(line, header)
                    elif in_waveform_points:
                        self._parse_waveform_point(line, header)
                    else:
                        self._parse_key_value(line, header)
        
        except Exception as e:
            logger.error(f"Error parsing MCG file {file_path}: {e}")
            raise
        
        return header
    
    def _parse_key_value(self, line: str, header: MCGHeader):
        """Parse key-value pairs from MCG file"""
        match = self.key_value_pattern.search(line)
        if not match:
            return
        
        key = match.group(1).strip()
        value = match.group(2).strip()
        
        try:
            if key == "Base Frequency (Hz)":
                header.base_frequency = float(value)
            elif key == "On Time (s)":
                header.on_time = float(value)
            elif key == "Off Time (s)":
                header.off_time = float(value)
            elif key == "Turn Off (s)":
                header.turn_off_time = float(value)
            elif key in ["Timing Mark (s)", "Waveform Timing Mark (s)"]:
                header.timing_mark = float(value)
            elif key == "Waveform Type":
                header.waveform_type = int(value)
            elif key == "Waveform Name":
                header.waveform_name = value
            elif key == "Transmitter Name":
                header.transmitter_name = value
            elif key == "Receiver Name":
                header.receiver_name = value
            elif key == "Configuration":
                header.configuration = int(value)
            elif key == "Units":
                header.units = int(value)
            elif key == "Number of channels":
                header.num_channels = int(value)
            elif key == "Time Domain":
                header.time_domain = value.upper() == "YES"
            elif key == "B Field response":
                header.bfield_response = value.upper() == "YES"
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing {key}={value}: {e}")
    
    def _parse_channel_time(self, line: str, header: MCGHeader):
        """Parse channel time window data"""
        match = self.channel_time_pattern.search(line)
        if match:
            try:
                start_time = float(match.group(2))
                end_time = float(match.group(3))
                header.channel_starts.append(start_time)
                header.channel_ends.append(end_time)
            except ValueError as e:
                logger.warning(f"Error parsing channel time: {e}")
    
    def _parse_waveform_point(self, line: str, header: MCGHeader):
        """Parse waveform data points"""
        match = self.waveform_point_pattern.search(line)
        if match:
            try:
                time = float(match.group(2))
                current = float(match.group(3))
                header.waveform_points.append(TimeCurrentPair(time, current))
            except ValueError as e:
                logger.warning(f"Error parsing waveform point: {e}")

def determine_field_type(units: Union[str, int]) -> str:
    """Determine field type based on units"""
    if isinstance(units, int):
        # MCG units mapping: 0=mV, 1=uV, 2=nV, 3=pV, 4=nT, 5=pT, 6=fT, 7=ppmHp, 8=%Ht, 9=nT/s, 10=pT/s
        b_field_units = {4, 5, 6, 7, 8}  # nT, pT, fT, ppmHp, %Ht
        dbdt_units = {9, 10}  # nT/s, pT/s
        voltage_units = {0, 1, 2, 3}  # mV, uV, nV, pV
        
        if units in b_field_units:
            return "B"
        elif units in dbdt_units or units in voltage_units:
            return "dBdT"
    else:
        # String-based unit detection
        units_lower = str(units).lower()
        b_field_indicators = ['nt', 'pt', 'tesla', 'gauss', 'magnetic', 'field', '%ht', 'bfield']
        dbdt_indicators = ['db/dt', 'dbdt', 'v/m', 'mv/m', 'derivative', 'rate', 'v', 'volt']
        
        if any(indicator in units_lower for indicator in b_field_indicators):
            return "B"
        elif any(indicator in units_lower for indicator in dbdt_indicators):
            return "dBdT"
    
    return "B"  # Default to B-field

def generate_channel_colors(channel_index: int, total_channels: int) -> Tuple[float, float, float]:
    """Generate color gradient for channel visualization"""
    if total_channels <= 1:
        return 0.5, 0.5, 0.5
    
    position = channel_index / (total_channels - 1)
    red = 0.25 + (position * 0.55)
    green = 0.75 - (position * 0.65)
    blue = 0.5
    
    return (max(0, min(1, red)), max(0, min(1, green)), max(0, min(1, blue)))

def parse_mcg_file(mcg_path: str, export_dir: str):
    """
    Parse MCG file and generate waveform and channel sampling CSV files.
    Updated with robust parsing from Go implementation.
    
    Args:
        mcg_path (str): Full path to .mcg file
        export_dir (str): Full path to export directory
    """
    try:
        parser = MCGParser()
        header = parser.parse_file(mcg_path)
        
        # Extract filename for output naming
        base_filename = Path(mcg_path).stem.lower()
        
        # Create waveform CSV
        if header.waveform_points:
            _create_waveform_csv(header, base_filename, export_dir)
        
        # Create channel sampling CSV
        if header.channel_starts and header.channel_ends:
            _create_sampling_csv(header, base_filename, export_dir)
            
    except Exception as e:
        logger.error(f"Error processing MCG file {mcg_path}: {e}")
        raise

def _create_waveform_csv(header: MCGHeader, base_filename: str, export_dir: str):
    """Create waveform CSV file"""
    waveform_dir = os.path.join(export_dir, 'Provus_Options', 'Waveforms')
    os.makedirs(waveform_dir, exist_ok=True)
    waveform_path = os.path.join(waveform_dir, f'{base_filename}.csv')
    
    # Normalize waveform points to 0-0.5 time scale
    if header.waveform_points:
        max_time = max(point.time for point in header.waveform_points)
        if max_time > 0:
            scaled_points = [(0.5 * point.time / max_time, point.current) 
                           for point in header.waveform_points]
        else:
            scaled_points = [(point.time, point.current) for point in header.waveform_points]
    else:
        scaled_points = []
    
    with open(waveform_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Waveform Name', base_filename])
        writer.writerow(['Base Frequency', f'{header.base_frequency:.6g}'])
        
        # Calculate zero time
        zero_time = header.timing_mark if header.timing_mark > 0 else 0.000000001
        writer.writerow(['Waveform Zero Time', f'{zero_time:.10f}'])
        writer.writerow(['Scaled Time', 'Current'])
        
        for time, current in scaled_points:
            writer.writerow([f'{time:.6f}', f'{current:.6f}'])

def _create_sampling_csv(header: MCGHeader, base_filename: str, export_dir: str):
    """Create channel sampling CSV file"""
    sampling_dir = os.path.join(export_dir, 'Provus_Options', 'Channel_Sampling_Schemes')
    os.makedirs(sampling_dir, exist_ok=True)
    
    num_channels = len(header.channel_starts)
    sampling_path = os.path.join(sampling_dir, f'{base_filename}_{num_channels}ch.csv')
    
    # Convert channel times from seconds to milliseconds
    channels_ms = [(start * 1000, end * 1000) 
                   for start, end in zip(header.channel_starts, header.channel_ends)]
    
    # Determine field type
    field_type = determine_field_type(header.units)
    if field_type == "dBdT":
        field_type = "dbdt"  # Match original format
    else:
        field_type = "b"
    
    with open(sampling_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Sampling Name', f'{base_filename}_{num_channels}ch'])
        writer.writerow(['Primary Time Gate', f'{channels_ms[0][0]:.3f}', f'{channels_ms[0][1]:.3f}'])
        writer.writerow(['Field Type', field_type])
        writer.writerow(['Channel Name', 'ChStart', 'ChEnd', 'Red', 'Green', 'Blue', 'LineWt'])
        
        for i, (start, end) in enumerate(channels_ms):
            red, green, blue = generate_channel_colors(i, num_channels)
            writer.writerow([
                f'Ch{i+1}',
                f'{start:.3f}',
                f'{end:.3f}',
                f'{red:.2f}',
                f'{green:.2f}',
                f'{blue:.2f}',
                '2'
            ]) 