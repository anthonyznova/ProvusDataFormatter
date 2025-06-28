# Provus Formatter

A Python GUI application that streamlines the process of preparing TEM/PEM (Transient Electromagnetic/Pulsed Electromagnetic) data files for import into Provus by automatically generating appropriate waveform and channel sampling scheme files, adding the appropriate flags to file headers, and updating project files. 


## Disclaimer

This tool is provided to assist with data formatting. Users are responsible for verifying the accuracy aof the generated waveform and sampling files for their specific data and requirements. Always maintain backups of original data files.


## Installation

### Download the installer .exe under releases and run

OR


### Install from Source

download and extract the ZIP file:
   ```bash
   cd ProvusFormatter-main
   ```
Install requirements in a Python environment:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Launch the Application

After installation, run the formatter using:
```bash
python main.py
```

### Basic Workflow

1. **File Selection**
   - Drag and drop TEM files into the application
   - Set the root directory for output files

2. **Review waveform and sampling**
   - Review detected parameters in the analysis table
   - Modify waveform and sampling scheme assignments if needed by DOUBLE CLICKING ON A ROW
   - Preview and edit waveform shapes using the built-in waveform editor
   - Select appropriate data styles for each file

3. **File Generation**
   - Click "Update Headers" to write waveform and sampling information to data files
   - Click "Update Project File" to create/update the Provus project file



### Output Structure

The tool creates the following directory structure in your root directory if it doesnt already exist.

```
root_directory/
├── Provus_Options/
│   ├── Waveforms/
│   │   ├── Square_5.200.csv
│   │   ├── UTEM_3.872.csv
│   │   └── ...
│   └── Channel_Sampling_Schemes/
│       ├── Square_5.200_14ch.csv
│       ├── UTEM_3.872_13ch.csv
│       └── ...
└── project.ppf
```

## File Formats

### Waveform Files
CSV format containing:
- Waveform name
- Base frequency
- Zero time
- Time-current pairs defining the waveform shape

### Channel Sampling Files
CSV format containing:
- Sampling scheme name
- Primary time gate
- Field type (B-field or dB/dt)
- Channel definitions (start time, end time, color coding)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
