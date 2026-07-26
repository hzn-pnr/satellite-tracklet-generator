# fits2png.py
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
import matplotlib.pyplot as plt
from astropy.io import fits
from skimage import exposure
from skimage.util import img_as_ubyte

def process_fits_to_png(fits_path, output_png_path):
    """
    Reads a FITS file, applies complex enhancement (Sqrt -> InvLog -> CLAHE -> Gamma),
    and saves as a PNG.
    """
    # Reading the FITS Image
    try:
        with fits.open(fits_path) as hdul:
            data = hdul[0].data
            if data.ndim > 2:
                data = data[0]
                
    except Exception as e:
        print(f"File reading error: {e}")
        return

    # Normalization
    # Based on Hazan (2026), p. 66, Eq. (3.36) 
    data = np.nan_to_num(data, nan=0.0, posinf=np.nanmax(data), neginf=np.nanmin(data))
    
    if np.max(data) == np.min(data):
        image = np.zeros_like(data, dtype=np.float64)
    else:
        image = (data - np.min(data)) / (np.max(data) - np.min(data))
    
    # Square Root Compression
    # Based on Hazan (2026), p. 66
    image = np.sqrt(image)

    # Inverse Logarithmic Correction
    # # Based on Hazan (2026), p. 67, Eq. (3.36) 
    try:
        image = exposure.adjust_log(image, gain=1, inv=True)
    except ValueError:
        pass 

    # CLAHE (Contrast Limited Adaptive Histogram Equalization)
    # Based on Hazan (2026), p. 67 
    image = exposure.equalize_adapthist(image, clip_limit=0.03)

    # Gamma Correction
    # Based on Hazan (2026), p. 67
    gamma_value = 0.5
    image = exposure.adjust_gamma(image, gamma=gamma_value)

    # Converting to 8-bit PNG
    final_image_ubyte = img_as_ubyte(image)
    
    # Save as PNG 
    plt.imsave(output_png_path, final_image_ubyte, cmap='gray')
    print(f"Converted FITS to PNG: {output_png_path}")

def fits_to_png_source(data, output_png):
    # This function performs a simple transformation for reference FITS (real) image.
    
    data = np.nan_to_num(data, nan=0.0, posinf=np.nanmax(data), neginf=np.nanmin(data))
    if np.max(data) != np.min(data):
        data = (data - np.min(data)) / (np.max(data) - np.min(data))
    else:
        data = np.zeros_like(data)
    
    rgb_data = np.stack([data, data, data], axis=-1)
    rgb_data = (rgb_data * 255).astype(np.uint8)
    
    plt.imsave(output_png, rgb_data)