# Provus Formatter

This tool streamlines the process of preparing TEM/PEM data files for import to provus by automatically generating appropriate waveform and channel sampling scheme files, adding the appropriate flags to file header, updating project file. 


## Disclaimer

This tool is provided to assist with data formatting. Users are responsible for verifying the accuracy and appropriateness of the generated waveform and sampling files for their specific data and requirements. Always maintain backups of original data files.


## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Dependencies

The following packages will be automatically installed:

- PyQt5 >= 5.15.0
- PyQtChart >= 5.15.0
- numpy >= 1.19.0
- pandas >= 1.3.0

### Install from Source

1. Clone the repository:
    git clone [(https://github.com/anthonyznova/ProvusFormatter)](https://github.com/anthonyznova/ProvusDataFormatter)

    or download the .zip 

    cd ProvusDataFormatter-main

2. Install requirements in python env

    pip install -r requirements.txt

## Usage

### Launch the Application

After installation, run the formatter using:
    python main.py

### Basic Workflow

1. **File Selection**
   - Drag and drop TEM/PEM files into the application
   - Set the root directory for output files

2. **Review waveform and sampling**
   - Review detected parameters in the analysis table
   - Modify waveform and sampling scheme assignments if needed
   - Preview and edit waveform shapes
   - Select appropriate data styles for each file

3. **File Generation**
   - Click "Update Headers" to write waveform and sampling information to data files
   - Click "Update Project File" to create/update the Provus project file

### Output Structure

The tool creates the following directory structure in your root directory:

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
