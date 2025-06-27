import re
import csv
from pathlib import Path
import logging
from collections import defaultdict
from .mcg_parser import TEMParser, MCGParser, determine_field_type, generate_channel_colors

logger = logging.getLogger(__name__)

class FileProcessor:
    def __init__(self, root_dir):
        if not root_dir:
            raise ValueError("Root directory must be specified")
        self.root_dir = Path(root_dir)
        if not self.root_dir.exists():
            raise ValueError(f"Root directory does not exist: {root_dir}")
        
        # Define regex patterns for header constants
        self.header_patterns = {
            'base_frequency': r'(?:BFREQ|BASEFREQ|BASEFREQUENCY)\s*[:=]\s*([\d.]+)',
            'units': r'UNITS\s*[:=]\s*(\w+)',
            'duty_cycle': r'(?:DUTYCYCLE|DUTY)\s*[:=]\s*(\S+)',
            'tx_waveform': r'TXWAVEFORM\s*[:=]\s*(\S+)',
            'system_info': r'(?:INSTRUMENT|SYSTEM|PRIMARYREMOVED)\s*[:=]\s*(\S+)',
            'survey_config': r'(?:CONFIG|CONFIGURATION)\s*[:=]\s*(\S+)',
            'data_type': r'DATATYPE\s*[:=]\s*(\S+)',
            'offtime': r'OFFTIME\s*[:=]\s*(\S+)',
        }
        
        # Add unit sets
        self.dbdt_units = {
            'uV', 'uV/A', 'uV/Am2', 'uV/m2',
            'nV', 'nV/A', 'nV/Am2', 'nV/m2',
            'pV', 'pV/A', 'pV/Am2', 'pV/m2',
            'nT/As', 'nT/Asm2',
            'pT/s', 'pT/As', 'pT/Asm2'
        }
        
        self.b_field_units = {
            'nT', 'nT/A', 'nT/Am2', 'nT/m2',
            'pT', 'pT/A', 'pT/Am2', 'pT/m2',
            'fT', 'fT/A', 'fT/Am2', 'fT/m2','ppm', 'ppmHp', 'ppt', 'pptHp',
            '%Ht', '%', 'ppmHz', 'pptHz',
            'ppmHx', 'pptHx', 'ppmHt', 'pptHt',
            'Ohm-m', 'S/m'
        }
        
        # Add PEM-specific patterns
        self.pem_patterns = {
            'survey_params': r'Metric.*Cable',
            'time_windows': r'-.*e.*'
        }
    
    def parse_file_headers(self, file_path):
        """Parse file for header constants and their values using robust parsers"""
        try:
            logger.info(f"\nProcessing: {Path(file_path).name}")
            file_path_obj = Path(file_path)
            
            # Determine file type and use appropriate parser
            if file_path_obj.suffix.lower() == '.tem':
                return self._parse_tem_file(file_path)
            elif file_path_obj.suffix.lower() == '.mcg':
                return self._parse_mcg_file(file_path)
            else:
                # Fallback to original parsing logic for other file types
                return self._parse_generic_file(file_path)
            
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {str(e)}", exc_info=True)
            return None
    
    def _parse_tem_file(self, file_path):
        """Parse TEM file using the robust TEM parser"""
        try:
            parser = TEMParser()
            header = parser.parse_file(file_path)
            
            # Convert TEM header to the format expected by the rest of the application
            results = {
                'base_frequency': f"{header.base_frequency:.3f}" if header.base_frequency else None,
                'units': header.units,
                'duty_cycle': header.duty_cycle if header.duty_cycle else 'Undefined',
                'tx_waveform': header.tx_waveform if header.tx_waveform else 'Undefined',
                'system_info': header.system_info or header.instrument,
                'survey_config': header.survey_config or header.configuration,
                'data_type': header.data_type,
                'offtime': header.off_time,
                'times_start': header.times_start,
                'times_end': header.times_end,
                'num_channels': len(header.times_start) if header.times_start else 0,
                'header_lines': []  # TEM parser doesn't store original lines
            }
            
            # Set default duty cycle for UTEM if not specified
            if not results['duty_cycle'] or results['duty_cycle'] == 'Undefined':
                if results['tx_waveform'] == 'UTEM':
                    results['duty_cycle'] = '100'
            
            logger.info(f"TEM parse results - Frequency: {results['base_frequency']}, "
                       f"Channels: {results['num_channels']}, TX: {results['tx_waveform']}")
            logger.info(f"Start times: {results['times_start']}")
            logger.info(f"End times: {results['times_end']}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error parsing TEM file {file_path}: {e}")
            return None
    
    def _parse_mcg_file(self, file_path):
        """Parse MCG file using the robust MCG parser"""
        try:
            parser = MCGParser()
            header = parser.parse_file(file_path)
            
            # Convert MCG header to the format expected by the rest of the application
            results = {
                'base_frequency': f"{header.base_frequency:.3f}" if header.base_frequency else None,
                'units': str(header.units) if header.units else None,
                'duty_cycle': 'Undefined',  # MCG files don't typically have duty cycle
                'tx_waveform': header.waveform_name or header.transmitter_name or 'Undefined',
                'system_info': header.transmitter_name or header.receiver_name,
                'survey_config': str(header.configuration) if header.configuration else None,
                'data_type': 'MCG',
                'offtime': str(header.off_time) if header.off_time else None,
                'times_start': [t * 1000 for t in header.channel_starts],  # Convert to ms
                'times_end': [t * 1000 for t in header.channel_ends],      # Convert to ms
                'num_channels': len(header.channel_starts),
                'header_lines': []  # MCG parser doesn't store original lines
            }
            
            logger.info(f"MCG parse results - Frequency: {results['base_frequency']}, "
                       f"Channels: {results['num_channels']}, TX: {results['tx_waveform']}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error parsing MCG file {file_path}: {e}")
            return None
    
    def _parse_generic_file(self, file_path):
        """Fallback parsing for non-TEM/MCG files (original logic)"""
        try:
            # Initialize results dictionary
            results = {
                'base_frequency': None,
                'units': None,
                'duty_cycle': None,
                'tx_waveform': 'Undefined',
                'system_info': None,
                'survey_config': None,
                'data_type': None,
                'offtime': None,
                'times_start': [],
                'times_end': [],
                'num_channels': None,
                'header_lines': []
            }
            
            times = None
            times_width = None
            current_unit = 'ms'  # Default to milliseconds
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Store original line
                    results['header_lines'].append(line)
                    
                    # Check for TIMESSTART/TIMESEND format first
                    if '/TIMESSTART' in line:
                        try:
                            values_str = line.split('=')[1].strip() if '=' in line else line.split('/TIMESSTART')[1].strip()
                            values_str = values_str.strip('(ms)').strip('(us)').strip()
                            results['times_start'] = [float(x.strip()) for x in values_str.split(',') if x.strip()]
                            logger.info(f"Found TIMESSTART: {results['times_start']}")
                        except Exception as e:
                            logger.warning(f"Could not parse TIMESSTART line: {line}")
                    
                    elif '/TIMESEND' in line:
                        try:
                            values_str = line.split('=')[1].strip() if '=' in line else line.split('/TIMESEND')[1].strip()
                            values_str = values_str.strip('(ms)').strip('(us)').strip()
                            results['times_end'] = [float(x.strip()) for x in values_str.split(',') if x.strip()]
                            results['num_channels'] = len(results['times_end'])
                            logger.info(f"Found TIMESEND: {results['times_end']}")
                        except Exception as e:
                            logger.warning(f"Could not parse TIMESEND line: {line}")
                    
                    # Check for TIMES/TIMESWIDTH format
                    elif '/TIMES(ms)=' in line or '/TIMES(us)=' in line:
                        try:
                            if 'us' in line:
                                current_unit = 'us'
                            values_str = line.split('=')[1].strip()
                            times = [float(x.strip()) for x in values_str.split(',') if x.strip()]
                            logger.info(f"Found TIMES: {times}")
                        except Exception as e:
                            logger.warning(f"Could not parse TIMES line: {line}")
                    
                    elif '/TIMESWIDTH(ms)=' in line or '/TIMESWIDTH(us)=' in line:
                        try:
                            values_str = line.split('=')[1].strip()
                            times_width = [float(x.strip()) for x in values_str.split(',') if x.strip()]
                            logger.info(f"Found TIMESWIDTH: {times_width}")
                        except Exception as e:
                            logger.warning(f"Could not parse TIMESWIDTH line: {line}")
                    
                    # Process other headers
                    parts = line.split()
                    for part in parts:
                        if part in ['&', '']:
                            continue
                        
                        for separator in ['=', ':']:
                            if separator in part:
                                key, value = part.split(separator, 1)
                                value = value.strip('," &')
                                key = key.upper()
                                
                                if key in ['BFREQ', 'BASEFREQ', 'BASEFREQUENCY']:
                                    try:
                                        base_freq = float(value)
                                        results['base_frequency'] = f"{base_freq:.3f}"
                                    except ValueError:
                                        results['base_frequency'] = value
                                    logger.info(f"Base Frequency: {results['base_frequency']}")
                                elif key == 'UNITS':
                                    results['units'] = value.strip('()')
                                    logger.info(f"Units: {value.strip('()')}")
                                elif key == 'TXWAVEFORM':
                                    results['tx_waveform'] = value
                                    logger.info(f"Tx Waveform: {value}")
                                elif key in ['DUTYCYCLE', 'DUTY']:
                                    try:
                                        duty = float(value)
                                        results['duty_cycle'] = f"{duty:.0f}"
                                    except ValueError:
                                        results['duty_cycle'] = value
                                    logger.info(f"Duty Cycle: {results['duty_cycle']}")
                                elif key in ['INSTRUMENT', 'SYSTEM', 'PRIMARYREMOVED']:
                                    results['system_info'] = value
                                elif key in ['CONFIG', 'CONFIGURATION']:
                                    results['survey_config'] = value
                                elif key == 'DATATYPE':
                                    results['data_type'] = value
                                elif key == 'OFFTIME':
                                    results['offtime'] = value
                                
                                break
                
                # Post-process times if using TIMES/TIMESWIDTH format
                if times and times_width and len(times) == len(times_width):
                    # Convert to milliseconds if needed
                    if current_unit == 'us':
                        times = [t / 1000.0 for t in times]
                        times_width = [w / 1000.0 for w in times_width]
                    
                    results['times_start'] = [t - w for t, w in zip(times, times_width)]
                    results['times_end'] = [t + w for t, w in zip(times, times_width)]
                    results['num_channels'] = len(times)
                    logger.info("Calculated time windows from TIMES/TIMESWIDTH")
                    logger.info(f"Start times: {results['times_start']}")
                    logger.info(f"End times: {results['times_end']}")
                
                # Post-process duty cycle based on rules
                if not results['duty_cycle']:
                    if results['tx_waveform'] == 'UTEM':
                        results['duty_cycle'] = '100'
                    else:
                        results['duty_cycle'] = 'Undefined'
                
                logger.info(f"Found {len(results['header_lines'])} header lines in {Path(file_path).name}")
                return results
            
        except Exception as e:
            logger.error(f"Error parsing generic file {file_path}: {str(e)}", exc_info=True)
            return None
    
    def _process_time_windows(self, line, results):
        """Process time window data from either format"""
        try:
            # Log the exact line we're processing, showing all characters
            logger.info(f"Processing time window line (raw): {repr(line)}")
            
            patterns = [
                # Updated pattern to handle more decimal places
                (r'/TIMESEND\([^)]+\)[=\s]*([0-9.,\s]+)', 'TIMESEND'),
                (r'/TIMESSTART\([^)]+\)[=\s]*([0-9.,\s]+)', 'TIMESSTART'),
                (r'/TIMES\([^)]+\)[=\s]*([0-9.,\s]+)', 'TIMES'),
            ]
            
            for pattern, type_name in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    logger.info(f"Matched {type_name} pattern")
                    values_str = match.group(1).strip()
                    logger.info(f"Raw values string: {repr(values_str)}")
                    
                    # Split on commas and convert to floats
                    values = []
                    for v in values_str.split(','):
                        v = v.strip()
                        if v:
                            try:
                                val = float(v)
                                values.append(val)
                            except ValueError:
                                logger.warning(f"Could not convert to float: {repr(v)}")
                                continue
                    
                    if values:
                        if type_name == 'TIMESEND':
                            results['num_channels'] = len(values)
                            results['times_end'] = values
                            logger.info(f"Number of Channels: {len(values)} from values: {values}")
                        return
                
            logger.warning(f"No patterns matched line: {repr(line)}")
                
        except Exception as e:
            logger.error(f"Error processing time windows in line: {repr(line)}")
            logger.error(f"Error: {str(e)}")
    
    def count_letters(self, file_path):
        """Count occurrences of 'a' and 'e' in file using regex"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Using regex to find letters regardless of context
                a_count = len(re.findall(r'a', content, re.IGNORECASE))
                e_count = len(re.findall(r'e', content, re.IGNORECASE))
                return a_count, e_count
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}", exc_info=True)
            return 0, 0
    
    def get_classification(self, a_count, e_count):
        """Classify based on letter counts"""
        if a_count == 0 and e_count == 0:
            return "none"
        elif a_count < 10 and e_count < 10:
            return "some"
        else:
            return "lots"
    
    def _determine_field_type(self, units):
        """Determine field type based on units"""
        if units in self.dbdt_units:
            return 'dbdt'
        elif units in self.b_field_units:
            return 'b'
        return 'b'  # Default to b if unknown

    def _generate_waveform_csv(self, header_data, output_dir):
        """Generate waveform CSV file based on header data"""
        base_freq = header_data.get('base_frequency')
        tx_waveform = header_data.get('tx_waveform', 'Undefined')
        duty_cycle = header_data.get('duty_cycle', '100')
        
        # Normalize duty cycle value
        try:
            # Convert to float and handle any decimal places
            duty_float = float(duty_cycle.strip())
            if abs(duty_float - 50.0) < 0.001:  # Check if it's approximately 50 (handles 50, 50.0, 50.000 etc)
                filename = f"50_Square_{base_freq}.csv"
                waveform_name = f"50_Square_{base_freq}"
            else:
                filename = f"Square_{base_freq}.csv"
                waveform_name = f"Square_{base_freq}"
        except ValueError:
            filename = f"Square_{base_freq}.csv"
            waveform_name = f"Square_{base_freq}"
        
        if not base_freq:
            return None
        
        # Determine waveform content based on conditions
        if tx_waveform == 'UTEM':
            filename = f"UTEM_{base_freq}.csv"
            waveform_name = f"UTEM_{base_freq}"
            content = [
                ['Waveform Name', waveform_name],
                ['BaseFrequency', base_freq],
                ['Waveform Zero Time', '0.0000'],
                ['Scaled Time', 'Current'],
                ['0.0000', '-1.000000'],
                ['0.0001', '1.000000'],
                ['0.5000', '1.000000']
            ]
        elif tx_waveform == 'Undefined':
            if '50_Square' in waveform_name:  # Check if it's 50% duty cycle
                content = [
                    ['Waveform Name', waveform_name],
                    ['BaseFrequency', base_freq],
                    ['Waveform Zero Time', '0.2501'],
                    ['Scaled Time', 'Current'],
                    ['0.0000', '0.000000'],
                    ['0.0001', '1.000000'],
                    ['0.2500', '1.000000'],
                    ['0.2501', '0.000000'],
                    ['0.5000', '0.000000']
                ]
            else:  # 100% duty cycle
                content = [
                    ['Waveform Name', waveform_name],
                    ['BaseFrequency', base_freq],
                    ['Waveform Zero Time', '0.0000'],
                    ['Scaled Time', 'Current'],
                    ['0.0000', '-1.000000'],
                    ['0.0001', '1.000000'],
                    ['0.5000', '1.000000']
                ]
        else:
            logger.warning(f"Unhandled waveform configuration: TX={tx_waveform}, Duty={duty_cycle}")
            return None
        
        # Create output path and check if file already exists
        output_path = output_dir / filename
        if output_path.exists():
            # Check if content matches
            with open(output_path, 'r') as f:
                existing_content = [line.strip().split(',') for line in f]
                if existing_content == content:
                    return filename
        
        # Write new file
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(content)
        
        logger.info(f"Created waveform file: {output_path}")
        return filename

    def _generate_sampling_csv(self, header_data, waveform_name, output_dir):
        """Generate sampling CSV file based on header data"""
        try:
            times_start = header_data.get('times_start', [])
            times_end = header_data.get('times_end', [])
            num_channels = header_data.get('num_channels')
            units = header_data.get('units')
            
            # Check for microsecond times in header lines
            time_unit = 'ms'  # default assumption
            header_lines = header_data.get('header_lines', [])
            for line in header_lines:
                if any(pattern in line for pattern in ['TIMESSTART(us)', 'TIMES(us)', 'TIMESEND(us)']):
                    time_unit = 'us'
                    logger.info(f"Detected microsecond time units in line: {line}")
                    break
            
            # Convert times to milliseconds if they're in microseconds
            if time_unit == 'us':
                logger.info(f"Converting times from microseconds to milliseconds")
                logger.info(f"Before conversion - Start times: {times_start}")
                logger.info(f"Before conversion - End times: {times_end}")
                
                times_start = [t / 1000.0 for t in times_start]
                times_end = [t / 1000.0 for t in times_end]
                
                logger.info(f"After conversion - Start times: {times_start}")
                logger.info(f"After conversion - End times: {times_end}")
            
            # Format base name with consistent decimal places
            base_name = Path(waveform_name).stem
            if 'UTEM' in base_name:
                formatted_name = base_name
            else:
                # Handle both regular Square and 50_Square cases
                parts = base_name.split('_')
                if parts[0] == '50':
                    freq = float(parts[2])  # For "50_Square_5.200" format
                    formatted_name = f"50_Square_{freq:.3f}"
                else:
                    freq = float(parts[1])  # For "Square_5.200" format
                    formatted_name = f"Square_{freq:.3f}"
            
            # Add channel suffix
            sampling_name = f"{formatted_name}_{num_channels}ch"
            filename = f"{sampling_name}.csv"
            
            # Store the sampling file name in header data
            header_data['sampling_file'] = filename
            
            output_path = output_dir / filename
            
            # Generate colors for all channels
            colors = [generate_channel_colors(i, num_channels) for i in range(num_channels)]
            
            with open(output_path, 'w', newline='') as f:
                # Write header rows without quotes
                f.write(f"Sampling Name,{sampling_name}\n")
                f.write(f"Primary Time Gate,{times_start[0]:.3f},{times_end[0]:.3f}\n")
                f.write(f"Field Type,{determine_field_type(units).lower()}\n")
                f.write("Channel Name,ChStart,ChEnd,Red,Green,Blue,LineWt\n")
                
                # Write channel data
                for i in range(num_channels):
                    red, green, blue = colors[i]
                    f.write(f"Ch{i+1},{times_start[i]:.3f},{times_end[i]:.3f},"
                           f"{red:.6f},{green:.6f},{blue:.6f},2\n")
            
            logger.info(f"Successfully created sampling CSV: {output_path}")
            return filename
            
        except Exception as e:
            logger.error(f"Error generating sampling CSV: {str(e)}", exc_info=True)
            return None

    def write_csv_results(self, results):
        """Write waveform and sampling scheme CSV files"""
        try:
            # Create directories if they don't exist
            waveform_dir = self.root_dir / "Provus_Options" / "Waveforms"
            sampling_dir = self.root_dir / "Provus_Options" / "Channel_Sampling_Schemes"
            waveform_dir.mkdir(parents=True, exist_ok=True)
            sampling_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Processing {len(results)} files for CSV generation")
            
            for file_path, result_data in results.items():
                logger.info(f"\nProcessing {Path(file_path).name}")
                header_data = result_data.get('header_data')
                if not header_data:
                    logger.warning(f"No header data for {file_path}")
                    continue
                
                # Generate waveform CSV
                waveform_name = self._generate_waveform_csv(header_data, waveform_dir)
                if waveform_name:
                    logger.info(f"Created waveform file: {waveform_name}")
                    
                    # Generate sampling CSV
                    sampling_name = self._generate_sampling_csv(header_data, waveform_name, sampling_dir)
                    if sampling_name:
                        logger.info(f"Created sampling file: {sampling_name}")
                    else:
                        logger.warning("Failed to create sampling file")
                else:
                    logger.warning("Failed to create waveform file")
        
        except Exception as e:
            logger.error(f"Error writing CSV results: {str(e)}", exc_info=True)

    def parse_pem_file(self, file_path):
        """Parse PEM file and extract key parameters."""
        with open(file_path, 'r') as file:
            content = file.readlines()
        
        # Initialize parameters
        survey_params = None
        time_windows = []
        found_time_window_section = False
        
        for line in content:
            line = line.strip()
            
            if not line:
                continue
                
            # Look for survey parameters line - modified to handle different formats
            if not survey_params and 'Metric' in line:
                try:
                    parts = line.strip().split()
                    # Ensure we have enough parts
                    if len(parts) >= 7:
                        # Different formats have parameters in the same positions
                        # Format: [survey_mode] Metric [sync_type] [time_base] [ramp_time] [n_gates] [n_readings]
                        survey_params = {
                            'survey_mode': parts[0],  # Borehole, Surface, etc.
                            'units': parts[1],        # Should be 'Metric'
                            'sync_type': parts[2],    # Crystal-Master, Cable, etc.
                            'time_base': float(parts[3]),
                            'ramp_time': int(parts[4]),
                            'n_gates': int(parts[5]),
                            'n_readings': int(parts[6])
                        }
                        logger.info(f"Found survey parameters: {survey_params}")
                except Exception as e:
                    logger.warning(f"Could not parse survey parameters from line: {line}. Error: {str(e)}")
                continue
            
            # Look for time window section
            if line.startswith('-') and 'e' in line.lower() and not found_time_window_section:
                found_time_window_section = True
                logger.info(f"Found time window section starting with: {line}")
                
            if found_time_window_section:
                if '$' in line:
                    logger.info(f"End of time window section at line: {line}")
                    break
                    
                try:
                    numbers = [x for x in line.split() if ('e' in x.lower() or 'e-' in x.lower())]
                    if numbers:
                        time_windows.extend([float(x) for x in numbers])
                except ValueError as ve:
                    logger.warning(f"Could not parse numbers in time window line: {line}. Error: {str(ve)}")
                    continue
        
        if survey_params is None:
            error_msg = "Could not find survey parameters line with 'Metric' keyword"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Calculate derived values
        base_freq = 1.0 / (4 * survey_params['time_base'] / 1000.0)
        ramp_time = survey_params['ramp_time'] / 1e6
        units = "nanoTesla/sec"  # Default for PEM
        num_gates = survey_params['n_gates']
        
        # Check if we have the expected number of time windows
        if len(time_windows) == 0:
            error_msg = "No time windows found in file"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"Parsed PEM file with {num_gates} gates, base frequency {base_freq:.3f}Hz")
        logger.info(f"Found {len(time_windows)} time windows")
        
        return base_freq, ramp_time, units, time_windows, num_gates

    def generate_pem_waveform_csv(self, filename, base_freq, ramp_time, output_file):
        """Generate waveform CSV file from PEM parameters."""
        try:
            points = [
                (0.0, 0.0),
                (0.02, 0.550671036),
                (0.04, 0.798103482),
                (0.06, 0.909282047),
                (0.08, 0.959237796),
                (0.1, 0.981684361),
                (0.14, 0.996302136),
                (0.16, 0.998338443),
                (0.20, 1.0),
                (0.25 - ramp_time, 1.0),
                (0.25, 0.0),
                (0.5, 0.0)
            ]
            
            # Find the second occurrence of zero amplitude
            zero_occurrences = [time for time, amplitude in points if amplitude == 0]
            zero_time = zero_occurrences[1] if len(zero_occurrences) >= 2 else 0.25
            
            with open(output_file, 'w', newline='') as file:
                writer = csv.writer(file)
                
                # Use a generic name based on frequency rather than filename
                writer.writerow(['Waveform Name', f'Crone_{base_freq:.1f}Hz'])
                writer.writerow(['Time Units', 'scaled'])
                writer.writerow(['Base Frequency', format(base_freq, '.3f')])
                writer.writerow(['Waveform Zero Time', format(zero_time, '.6f')])
                writer.writerow(['Scaled Time', 'Current'])
                
                for time, current in points:
                    writer.writerow([format(time, '.6f'), format(current, '.6f')])
            
            # Return just the filename, not the full path
            return Path(output_file).name
                    
        except Exception as e:
            logger.error(f"Error generating {output_file}: {str(e)}")
            return None

    def generate_pem_sampling_csv(self, filename, time_windows, num_gates, units, output_file):
        """Generate sampling CSV file from PEM time windows."""
        try:
            with open(output_file, 'w', newline='') as file:
                writer = csv.writer(file)
                
                # Use a generic name based on frequency and channel count
                writer.writerow(['Sampling Name', f'Crone_{num_gates}ch'])
                
                if len(time_windows) >= 2:
                    pp_start = time_windows[0] * 1000
                    pp_end = time_windows[1] * 1000
                    writer.writerow(['Primary Time Gate', f"{pp_start:.3f}", f"{pp_end:.3f}"])
                else:
                    writer.writerow(['Primary Time Gate', '-0.2', '-0.1'])
                
                # Determine field type based on units
                field_type = 'dBdT' if units and 'sec' in units.lower() else 'B'    
                writer.writerow(['Field Type', field_type])
                writer.writerow(['Channel Name', 'ChStart', 'ChEnd', 'Red', 'Green', 'Blue', 'LineWt'])
                
                # Generate colors for all channels
                colors = [generate_channel_colors(i, num_gates) for i in range(num_gates)]
                
                if len(time_windows) > 3:
                    for i in range(min(num_gates, len(time_windows)-3)):
                        ch_num = i + 1
                        start_time = time_windows[2] if i == 0 else time_windows[i+2]
                        end_time = time_windows[i+3]
                        
                        start_time *= 1000
                        end_time *= 1000
                        
                        # Use the generated colors
                        red, green, blue = colors[i]
                        
                        writer.writerow([
                            f"Ch{ch_num}",
                            f"{start_time:.3f}",
                            f"{end_time:.3f}",
                            f"{red:.6f}",
                            f"{green:.6f}",
                            f"{blue:.6f}",
                            '2'
                        ])
                
                pp_start = time_windows[0] * 1000
                pp_end = time_windows[1] * 1000
                writer.writerow(['PP', f"{pp_start:.3f}", f"{pp_end:.3f}", 
                               '0', '0.299774', '0.996094', '2'])
                
                # Return just the filename, not the full path
                return Path(output_file).name
                        
        except Exception as e:
            logger.error(f"Error generating {output_file}: {str(e)}")
            return None

    def generate_channel_colors(self, num_channels):
        """
        Generate colors for channels with a simple increment/decrement pattern.
        Red increases by 0.05, Green decreases by 0.05, Blue stays at 0.5
        
        Args:
            num_channels: Number of channels to generate colors for
            
        Returns:
            List of (red, green, blue) tuples with values between 0 and 1
        """
        colors = []
        
        # Starting values
        red_start = 0.25    # Starts at 0.25
        green_start = 0.75  # Starts at 0.75
        blue = 0.5         # Constant at 0.5
        
        for i in range(num_channels):
            red = red_start + (i * 0.05)
            green = green_start - (i * 0.05)
            colors.append((red, green, blue))
        
        return colors 