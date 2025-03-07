import re
import os
import csv
from pathlib import Path

def parse_mcg_file(mcg_path, export_dir):
    """
    Parse MCG file and generate waveform and channel sampling CSV files.
    
    Args:
        mcg_path (str): Full path to .mcg file
        export_dir (str): Full path to export directory
    """
    # Read MCG file content
    with open(mcg_path, 'r') as f:
        content = f.read()

    # Extract filename without extension for naming output files
    base_filename = Path(mcg_path).stem.lower()
    
    # Define regex patterns
    patterns = {
        'waveform_points': r'START OF STANDARD WAVEFORM\n.*?\n(.*?)END OF STANDARD WAVEFORM',
        'base_frequency': r'Base Frequency \(Hz\)\s*:\s*([0-9.]+)',
        'timing_mark': r'Waveform Timing Mark \(s\)\s*:\s*([0-9.]+)',
        'channel_times': r'START OF CHANNEL TIMES\n.*?\n(.*?)END OF CHANNEL TIMES',
        'units': r'Units\s*:\s*(\d+)',
        'unit_types': r'Unit Types\s*:.*?(\d+=.*?)(?:\n|$)'
    }
    
    # Extract data using regex
    matches = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, content, re.DOTALL)
        if match:
            matches[key] = match.group(1)
    
    # Process waveform data
    waveform_lines = [line.strip().split() for line in matches['waveform_points'].strip().split('\n')]
    waveform_points = [(float(line[1]), float(line[2])) for line in waveform_lines]
    
    # Scale times to 0-0.5 range
    max_time = max(point[0] for point in waveform_points)
    scaled_points = [(0.5 * time/max_time if time != 0 else 0.0, amp) for time, amp in waveform_points]
    
    # Create waveform CSV
    waveform_dir = os.path.join(export_dir, 'Provus_Options', 'Waveforms')
    os.makedirs(waveform_dir, exist_ok=True)
    waveform_path = os.path.join(waveform_dir, f'{base_filename}.csv')
    
    with open(waveform_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Waveform Name', base_filename])
        writer.writerow(['Base Frequency', matches['base_frequency']])
        writer.writerow(['Waveform Zero Time', matches['timing_mark']])
        writer.writerow(['Scaled Time', 'Current'])
        for time, amp in scaled_points:
            writer.writerow([f'{time:.6f}', f'{amp:.6f}'])
    
    # Process channel data
    channel_lines = [line.strip().split() for line in matches['channel_times'].strip().split('\n')]
    channels = [(float(line[1])*1000, float(line[2])*1000) for line in channel_lines]  # Convert to ms
    num_channels = len(channels)
    
    # Determine field type based on units
    unit_num = int(matches['units'])
    dbdt_units = ['uV', 'nV', 'pV', 'nT/s', 'pT/s']
    unit_map = {}
    for unit_def in matches['unit_types'].split(','):
        num, unit = unit_def.strip().split('=')
        unit_map[int(num)] = unit.strip()
    
    field_type = 'dbdt' if unit_map[unit_num] in dbdt_units else 'b'
    
    # Create channel sampling CSV
    sampling_dir = os.path.join(export_dir, 'Provus_Options', 'Channel_Sampling_Schemes')
    os.makedirs(sampling_dir, exist_ok=True)
    sampling_path = os.path.join(sampling_dir, f'{base_filename}_{num_channels}ch.csv')
    
    with open(sampling_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Sampling Name', f'{base_filename}_{num_channels}ch'])
        writer.writerow(['Primary Time Gate', f'{channels[0][0]:.3f}', f'{channels[0][1]:.3f}'])
        writer.writerow(['Field Type', field_type])
        writer.writerow(['Channel Name', 'ChStart', 'ChEnd', 'Red', 'Green', 'Blue', 'LineWt'])
        
        for i, (start, end) in enumerate(channels, 1):
            red = 0.25 + (i-1) * 0.05
            green = 0.75 - (i-1) * 0.05
            writer.writerow([
                f'Ch{i}',
                f'{start:.3f}',
                f'{end:.3f}',
                f'{red:.2f}',
                f'{green:.2f}',
                '0.50',
                '2'
            ]) 