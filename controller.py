# controller.py
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
from core.params import SceneParameters
from core.simulator import TrackletSimulator
from core.convert import ImageConverter
from core.visualize import StellariumVisualizer
from core.frame_util import add_frame_to_png
from core.wcs_helper import update_fits_wcs

class TrackletSimulationController:
    def __init__(self, txt_file_path):
        self.txt_file_path = txt_file_path
        self.params = SceneParameters(txt_file_path).params
        self.outputs = {}
        self.log_callback = print 
        self.progress_callback = None
        self.stop_check_callback = None

    def set_progress_callback(self, callback_func):
        self.progress_callback = callback_func

    def set_stop_check_callback(self, callback_func):
        self.stop_check_callback = callback_func

    def _check_stop(self):
        if self.stop_check_callback:
            self.stop_check_callback()

    def set_log_callback(self, callback_func):
        self.log_callback = callback_func

    def log(self, message):
        print(message) 
        if self.log_callback:
            self.log_callback(message)

    def run(self):
        self._check_stop()
        self.log(" Started: Tracklet simulation...")

        self.params['check_stop_func'] = self.stop_check_callback

        def scaled_progress(val):
            if self.progress_callback:
                self.progress_callback(int(val * 0.7))
        
        # Add to parameters for the simulator to use.
        self.params['progress_callback'] = scaled_progress
        # ------------------------

        if self.progress_callback: self.progress_callback(5) 

       
        base_name_input = self.params.get('output_name', 'final_output').strip()
        if base_name_input.lower().endswith('.png') or base_name_input.lower().endswith('.fits'):
             base_name_clean = os.path.splitext(base_name_input)[0]
        else:
             base_name_clean = base_name_input

        
        final_output_directory = os.path.join(self.params["output"], "output_tracklet")
        os.makedirs(final_output_directory, exist_ok=True)

        # -----------------------------------------------------------
        # Simulation
        # -----------------------------------------------------------
        self._check_stop()
        self.log("  Calculating tracklet...")
        sim_result = TrackletSimulator(self.params).run()
        self.outputs["tracklet"] = sim_result

        if self.progress_callback: self.progress_callback(75)
        
        path_adu_fits = sim_result["paths"]["adu"]       # SIMU.fits
        path_photon_fits = sim_result["paths"]["photon"] # eSIMU.fits

        self.log("  Updating FITS WCS headers...")
        update_fits_wcs(path_adu_fits, self.params)
        update_fits_wcs(path_photon_fits, self.params)

        # -----------------------------------------------------------
        # Convert PNG
        # -----------------------------------------------------------
        self._check_stop()
        self.log("  Generating PNG images...")

        png_name_simu = f"{base_name_clean}_SIMU.png"
        png_name_esimu = f"{base_name_clean}_eSIMU.png"

        path_simu_png = os.path.join(final_output_directory, png_name_simu)
        path_esimu_png = os.path.join(final_output_directory, png_name_esimu)


        self._check_stop()
        converter = ImageConverter()
        converter.convert(path_adu_fits, path_simu_png)     # SIMU (Normal)
        converter.convert(path_photon_fits, path_esimu_png) # eSIMU (Photon)

        if self.progress_callback: self.progress_callback(85)

        self.outputs["png"] = path_esimu_png 

        # -----------------------------------------------------------
        # Stellarium 
        # -----------------------------------------------------------
        stellarium_scripts_path = self.params.get('stellarium_scripts_path', '')
        
        self._check_stop()
        if stellarium_scripts_path and os.path.exists(stellarium_scripts_path):
            self.log(f"  Preparing Stellarium integration...")
            
            stel_images_dir = os.path.join(stellarium_scripts_path, "images")
            os.makedirs(stel_images_dir, exist_ok=True)
            
            ref_image_path = self.params.get('reference_image', '').strip()
            
            if ref_image_path:
                source_image_path = path_esimu_png
                target_image_name = png_name_esimu
                self.log(f" [Mode] Reference image detected -> Using eSIMU (Photon).")
            else:
                source_image_path = path_simu_png
                target_image_name = png_name_simu
                self.log(f" [Mode] No reference image -> Using SIMU (ADU).")
        
       
            stel_image_dest = os.path.join(stel_images_dir, target_image_name)
            
            try:
                shutil.copy(source_image_path, stel_image_dest)
                self.log(f"  Image copied: {stel_image_dest}")
                
    
                add_frame_val = self.params.get('add_frame', False)
                if str(add_frame_val).lower() == 'true': 
                    self.log("  Adding frame...")
                    frame_color = self.params.get('frame_color', '#FF0000')
                    try:
                        add_frame_to_png(
                            image_path=stel_image_dest, 
                            output_path=stel_image_dest,
                            color=frame_color,
                            thickness=5
                        )
                    except Exception as e:
                        self.log(f" [ERROR] Frame error: {e}")
            
  
                ssc_path = os.path.join(stellarium_scripts_path, "tracklet.ssc")
                
                self.log("  Updating Stellarium script (.ssc)...")
                
                StellariumVisualizer(self.params).run(
                    image_width=self.params["shape"][1],
                    image_height=self.params["shape"][0],
                    pixel_scale=self.params["pixel_scale"],
                    fits_path=path_adu_fits,    
                    image_path=stel_image_dest,  
                    scc_path=ssc_path,
                    wcs_matrix=self.params.get("cd"),
                    rotation=self.params.get("rotation")
                )
                self.log(f"  SSC created: {ssc_path}")

            except Exception as e:
                self.log(f" [ERROR] Stellarium operations error: {e}")

        else:
            self.log(" [WARNING] Stellarium Script path not set.")

        self.log(" Simulation completed.")

        if self.progress_callback: self.progress_callback(100)
        
        return self.outputs