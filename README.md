# satellite-tracklet-generator

This repository contains the optical tracklet simulation software developed by Pınar Hazan as part of her MSc thesis. It provides a unified environment for generating synthetic astronomical images of satellite tracklets, combining a PyQt5-based graphical interface with independent Python modules for each simulation stage.

Users input simulation parameters through the GUI, which passes them to the underlying modules responsible for:

- Satellite motion simulation — simulating the satellite's trajectory across the field of view
- Background star field generation — populating the scene with realistic stellar backgrounds
- Image synthesis — rendering the final visual output

The pipeline produces synthetic astronomical images in both FITS and PNG formats, replicating what a telescope's sensor would capture during a satellite transit. Generated images can additionally be imported into Stellarium for visual validation and assessment.

## Software Foundations and Extensions

This project builds upon **SPIMT** and **StellariumRC**, which were adapted for the integrated tracklet simulation workflow.

[SPIMT](https://github.com/Dujunju/SPIMT) is a photon-mapping-based method for generating realistic photometric images of moving targets. Its two-stage workflow—photon tracing and image rendering—considers the telescope tracking mode, point spread function, light sources, and CCD characteristics. Within this project, SPIMT was extended to support satellite trajectory calculations using **SP3 precise-orbit data**, in addition to its original TLE-based workflow.

[StellariumRC](https://github.com/k96e/StellariumRC) provides access to the Stellarium Remote Control API. Its modules were adapted and integrated to display the generated images in Stellarium according to the correct observation time, observer location, and celestial position.

## Thesis

This software was developed within the scope of the following MSc thesis:

> **Optical Tracklet Simulation for Space Surveillance and Tracking**  
> Pınar Hazan  
> Department of Geomatics Engineering  
> Hacettepe University  
> 2026

Thesis link:

[https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=5T1_CZ5-UGb9QCmoURec4EMQht9TqDr4HGGTjeH8RuUm_cisInFxS0WwA3dpi2BJ]

### Suggested Citation

```bibtex
@mastersthesis{hazan2026optical,
  author  = {Hazan, Pınar},
  title   = {Optical Tracklet Simulation for Space Surveillance and Tracking},
  school  = {Hacettepe University},
  year    = {2026},
  type    = {Master's Thesis},
  url     = {https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=5T1_CZ5-UGb9QCmoURec4EMQht9TqDr4HGGTjeH8RuUm_cisInFxS0WwA3dpi2BJ}
}
```

When using this software in academic work, please cite both the thesis and this repository.

## Example Outputs

### Graphical User Interface

![Satellite Tracklet Generator interface](docs/images/application_interface.png)
![Satellite Tracklet Generator interface](docs/images/application_interface2.png)

### Synthetic Satellite Tracklet

![Synthetic satellite tracklet](docs/images/synthetic_tracklet.png)

### Stellarium Visualisation

![Stellarium visualisation](docs/images/stellarium_visualisation.png)

## Software Workflow

The software combines the individual simulation stages through a unified workflow.

```text
User-defined parameters
        │
        ▼
Graphical user interface
        │
        ▼
Observation and sensor configuration
        │
        ▼
Orbit-source selection
   ┌────┴────┐
   │         │
  TLE       SP3
   │         │
   └────┬────┘
        ▼
Satellite position and apparent-motion calculation
        │
        ▼
Background-star catalogue query
        │
        ▼
Photon-based image simulation
        │
        ▼
Telescope, atmosphere and detector modelling
        │
        ▼
FITS image generation
        │
        ▼
PNG conversion
        │
        ▼
Stellarium sky-overlay generation
```
---
## Requirements

### Software Requirements

- Stellarium desktop application
- Internet connection for catalogue and TLE queries

### Python Requirements

Python dependencies are listed in:

```text
requirements.txt
```

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/hzn-pnr/satellite-tracklet-generator.git
cd satellite-tracklet-generator
```

### 2. Create a Virtual Environment

#### Windows Command Prompt

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Configuration

Some machine-specific settings and account credentials are stored locally in a `config.ini` file.

Example configuration:

```ini
[spacetrack]
username = YOUR_SPACE_TRACK_USERNAME
password = YOUR_SPACE_TRACK_PASSWORD

[paths]
stellarium_scripts = PATH_TO_STELLARIUM_SCRIPTS_DIRECTORY
```
---

## Space-Track Configuration

A Space-Track.org account is required only when the automatic TLE-retrieval functionality is used.

Users may alternatively:

- Enter TLE lines manually
- Use a local SP3 file

Enter the Space-Track account information into the local configuration file or through the relevant application configuration window.

---

## Stellarium Setup

Stellarium must be installed separately. It is not distributed with this repository.

### 1. Install Stellarium

Download and install the desktop version of Stellarium:

[Stellarium Official Website](https://stellarium.org/)

### 2. Enable the Remote Control Plugin

The Stellarium Remote Control plugin must be enabled before the generated images can be visualised.

1. Open Stellarium.
2. Open the **Configuration Window**.
3. Go to the **Plugins** tab.
4. Select **Remote Control**.
5. Enable **Load at startup**.
6. Restart Stellarium.
7. Open the Remote Control plugin settings.
8. Start the Remote Control server.
9. Enable automatic server startup if desired.
10. Keep the port set to `8090`.

The software communicates with Stellarium through:

```text
http://127.0.0.1:8090
```

The connection can be tested by opening the following address in a browser while Stellarium is running:

```text
http://localhost:8090
```

### 3. Configure the Stellarium Scripts Directory

A typical Stellarium scripts path on Windows is:

```text
C:\Users\<USERNAME>\AppData\Roaming\Stellarium\scripts
```

Select this directory through the application configuration menu or add it to `config.ini`.

The software may create the following files in the scripts directory:

```text
scripts/
├── tracklet.ssc
└── images/
    ├── <output_name>_SIMU.png
    ├── <output_name>_eSIMU.png
    └── [optional reference image]
```

---

## Running the Application

Before starting the simulation:

1. Start Stellarium.
2. Confirm that the Remote Control server is running.
3. Activate the Python virtual environment.
4. Start the graphical application.

```bash
python gui.py
```
---






