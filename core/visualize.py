# core/visualize.py
"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com
"""
import os
import shutil
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from core.convert import ImageConverter

try:
    import StellariumRC
    HAS_STELLARIUM_RC = True
except ImportError:
    HAS_STELLARIUM_RC = False
    print("WARNING: StellariumRC module not found.")

# Based on Hazan (2026), p. 59, Eq. (3.30) and Eq. (3.31)
def compute_cd_matrix(pixel_scale_arcsec, rotation_deg, parity=-1):
    scale_deg = pixel_scale_arcsec / 3600.0
    theta = np.deg2rad(-rotation_deg)
    cd = scale_deg * np.array([
        [-np.cos(theta), np.sin(theta)],
        [-np.sin(theta), -np.cos(theta)]
    ])
    return parity * cd


class StellariumVisualizer:
    def __init__(self, params):
        self.params = params

    def run(self, image_width, image_height, pixel_scale, fits_path, 
            image_path, scc_path, wcs_matrix=None, rotation=None):

        # Stellarium connection
        stellarium_connected = False
        s = None
        if HAS_STELLARIUM_RC:
            try:
                s = StellariumRC.Stellarium()
                s.location.setLocation(
                    latitude=self.params["latitude"],
                    longitude=self.params["longitude"],
                    altitude=self.params["elevation"]
                )
                stellarium_connected = True
            except Exception:
                pass

        # Calculate image corner coordinates
        corners = self._compute_corners(
            fits_path, image_width, image_height, pixel_scale,
            wcs_matrix=wcs_matrix, rotation=rotation
        )

        script_dir = os.path.dirname(scc_path)
        stellarium_image_dir = os.path.join(script_dir, "images")
        os.makedirs(stellarium_image_dir, exist_ok=True)

        reference_image_gui_path = self.params.get("reference_image")
        final_ref_filename = None 

        if reference_image_gui_path and os.path.exists(reference_image_gui_path):
            try:
                ref_basename = os.path.basename(reference_image_gui_path)
                target_name = os.path.splitext(ref_basename)[0] + "_ref.png"
                target_full_path = os.path.join(stellarium_image_dir, target_name)
                
                if not os.path.exists(target_full_path):
                    if reference_image_gui_path.lower().endswith(('.fits', '.fit')):
                        ref_data = fits.getdata(reference_image_gui_path)
                        ImageConverter().convert_for_reference(ref_data, target_full_path)
                    else:
                        shutil.copy(reference_image_gui_path, target_full_path)

                final_ref_filename = target_name 
            except Exception as e:
                print(f"Ref işleme hatası: {e}")

        self._generate_scc_script(
            simulated_image_path=image_path,
            simulated_corners=corners,
            reference_filename=final_ref_filename,
            scc_path=scc_path
        )

        if stellarium_connected and s:
            try:
                s.scripts.runScript(os.path.basename(scc_path))
            except Exception:
                pass

    def _compute_corners(self, fits_path, image_width, image_height, pixel_scale, 
                         wcs_matrix=None, rotation=None):
     
        ra = self.params["A0"]
        dec = self.params["D0"]
        crpix_x = self.params["dx"]
        crpix_y = self.params["dy"]

        wcs = WCS(naxis=2)
        wcs.wcs.crval = [ra, dec] 
        wcs.wcs.ctype = ['RA---TAN-SIP', 'DEC--TAN-SIP']
        wcs.wcs.crpix = [crpix_x, crpix_y] 

        if rotation is not None:
            wcs.wcs.cd = compute_cd_matrix(pixel_scale_arcsec=pixel_scale,
                                           rotation_deg=rotation,
                                           parity=-1)
        elif wcs_matrix is not None:
            wcs.wcs.cd = np.array(wcs_matrix)
        else:
            raise ValueError("WCS verisi eksik.")

        corner_pixels = [
            [0, image_height - 1],
            [image_width - 1, image_height - 1],
            [image_width - 1, 0],
            [0, 0]
        ]

        return wcs.wcs_pix2world(corner_pixels, 0)


    def _generate_scc_script(self, simulated_image_path, simulated_corners, 
                             reference_filename, scc_path):
        
        os.makedirs(os.path.dirname(scc_path), exist_ok=True)

     
        sim_basename = os.path.basename(simulated_image_path)
        relative_sim_path = f"images/{sim_basename}"
        

        relative_ref_path = f"images/{reference_filename}" if reference_filename else None

        center_ra = self.params["A0"]
        center_dec = self.params["D0"]
        iso_time = self.params["time_init"]

        
        lines = [
            'core.clear("natural");',
            ''
        ]

      
        if relative_ref_path:
            lines.append(f'core.loadSkyImage("sky_overlay_ref", "{relative_ref_path}",')
            for ra, dec in simulated_corners:
                lines.append(f"    {ra:.6f}, {dec:.6f},")
            lines.append("    0.6, 1, true);") 
            lines.append('StelSkyLayerMgr.showLayer("sky_overlay_ref", true);')
            lines.append("")

        # Based on Hazan (2026), p. 69
        lines.append(f'core.loadSkyImage("sky_overlay_sim", "{relative_sim_path}",')
        for ra, dec in simulated_corners:
            lines.append(f"    {ra:.6f}, {dec:.6f},")
        lines.append("    0.6, 1, true);")
        lines.append('StelSkyLayerMgr.showLayer("sky_overlay_sim", true);')
        lines.append("")

        lines.append(f'core.setDate("{iso_time}", "utc");')
        lines.append('core.setTimeRate(0);')
        lines.append(f'core.moveToRaDecJ2000({center_ra}, {center_dec}, 5.0);')
        lines.append('core.wait(5.5);')
        
        with open(scc_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        print(f" SSC dosyası yazıldı (Sade): {scc_path}")