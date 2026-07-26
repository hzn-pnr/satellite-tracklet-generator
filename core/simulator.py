# core/simulator.py
"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com
"""
import numpy as np
import os
from astropy.io import fits
from sst_main import img_generator


class TrackletSimulator:
    def __init__(self, params):
        self.params = params

    def run(self):
        output_dir = os.path.join(self.params['output'], "output_tracklet")
        os.makedirs(output_dir, exist_ok=True)


        base_name = os.path.splitext(self.params.get('output_name', 'final'))[0]

        img_adu_path = os.path.join(output_dir, f"{base_name}_SIMU.fits")
        img_photon_path = os.path.join(output_dir, f"{base_name}_eSIMU.fits")

        self.params['img_photo'] = img_photon_path
        self.params['img_adu'] = img_adu_path

        shape = self.params['shape']


        # Run simulation
        img_generator(self.params)

        # Read the FITS file and restore it from memory.
        image_adu = fits.getdata(img_adu_path)
        image_photon = fits.getdata(img_photon_path)

        return {
            "adu": image_adu,
            "photon": image_photon,
            "paths": {
                "adu": img_adu_path,
                "photon": img_photon_path
            }
        }
