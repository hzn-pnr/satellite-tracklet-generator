# core/convert.py
"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com
"""

from fits2png import process_fits_to_png, fits_to_png_source

class ImageConverter:
    def __init__(self):
        pass

    def convert(self, fits_path, output_png_path):
        """
        Converts FITS file at 'fits_path' to PNG using the new process pipeline.
        
        Parameters:
            fits_path: str, path to input FITS file
            output_png_path: str, path to output PNG file
        """
        process_fits_to_png(fits_path, output_png_path)
        return output_png_path
    

    def convert_for_reference(self, fits_array, output_png_path):
        fits_to_png_source(fits_array, output_png_path)
        return output_png_path