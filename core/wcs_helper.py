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
from astropy.io import fits

def update_fits_wcs(fits_path, params):
    """
    Updates the header of the given FITS file according to the coordinate and optical information in the parameters.
    """
    try:
        
        with fits.open(fits_path, mode='update') as hdul:
            header = hdul[0].header

            # Image Dimensions and Center Pixel (CRPIX)
            ny, nx = params['shape']
            
            # FITS pixels start from 1 
            # Center: (N / 2) + 0.5
            crpix1 = nx / 2.0 + 0.5
            crpix2 = ny / 2.0 + 0.5

            # Reference Coordinates (CRVAL) 
            crval1 = float(params['A0'])
            crval2 = float(params['D0'])

            # CD Matrix
            if params.get('cd') is not None:
                # params['cd'] formatı: [[cd1_1, cd1_2], [cd2_1, cd2_2]]
                cd_matrix = np.array(params['cd']) 
                cd1_1, cd1_2 = cd_matrix[0, 0], cd_matrix[0, 1]
                cd2_1, cd2_2 = cd_matrix[1, 0], cd_matrix[1, 1]
            
            else:
                scale_arcsec = float(params['pixel_scale'])
                rot_deg = float(params.get('rotation', 0.0))
                
                scale_deg = scale_arcsec / 3600.0
                theta = np.deg2rad(-rot_deg) 
                parity = -1                  
                
            
                base_cd = scale_deg * np.array([
                    [-np.cos(theta), np.sin(theta)],
                    [-np.sin(theta), -np.cos(theta)]
                ])
                
                cd_matrix = parity * base_cd
        
                cd1_1, cd1_2 = cd_matrix[0, 0], cd_matrix[0, 1]
                cd2_1, cd2_2 = cd_matrix[1, 0], cd_matrix[1, 1]

   
            
            # Observation Time
            header['DATE-OBS'] = (params['time_init'], 'Observation Date (UTC)')
            
            # Projection Type (Gnomonic - Standard)
            header['CTYPE1'] = ('RA---TAN', 'Right Ascension, gnomonic projection')
            header['CTYPE2'] = ('DEC--TAN', 'Declination, gnomonic projection')

            # Reference Pixels
            header['CRPIX1'] = (crpix1, 'Reference pixel along axis 1')
            header['CRPIX2'] = (crpix2, 'Reference pixel along axis 2')

            # Reference Coordinates
            header['CRVAL1'] = (crval1, 'Right Ascension at reference pixel (deg)')
            header['CRVAL2'] = (crval2, 'Declination at reference pixel (deg)')

            # CD Matrix
            header['CD1_1'] = (cd1_1, 'Transformation matrix element 1,1')
            header['CD1_2'] = (cd1_2, 'Transformation matrix element 1,2')
            header['CD2_1'] = (cd2_1, 'Transformation matrix element 2,1')
            header['CD2_2'] = (cd2_2, 'Transformation matrix element 2,2')

    
            header['PIXSCALE'] = (params['pixel_scale'], 'Pixel scale in arcsec/pixel')
            header['ROTATION'] = (params.get('rotation', 0.0), 'Image rotation in degrees')
            header['TELESCOP'] = ('Simulated', 'Source of the data')

            # Save changes
            hdul.flush()
            print(f"Header updated successfully for: {fits_path}")

    except Exception as e:
        print(f"Error updating FITS header: {e}")