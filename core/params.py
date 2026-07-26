# core/params.py
"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com
"""
class SceneParameters:
    def __init__(self, txt_path):
        self.params = self.load_params(txt_path)

    def load_params(self, path):
        parsed = {}
        with open(path, 'r') as file:
            for line in file:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    parsed[key.strip()] = value.strip()

       
        def to_float(key, default=None): 
            val = parsed.get(key, '').strip()
            try:
                return float(val)
            except (ValueError, TypeError):
                return default
        def to_int(key): return int(parsed[key]) if key in parsed else 0
        def to_tuple(x, y): return (to_int(x), to_int(y))

        mag_min = to_float('mag_range_min', -10)
        mag_max = to_float('mag_range_max', 15)

        # Based on Hazan (2026), p. 41-44
        return {
            'A0': to_float('A0'),
            'D0': to_float('D0'),
            'latitude': to_float('latitude'),
            'longitude': to_float('longitude'),
            'elevation': to_float('elevation'),
            'exposure': to_float('exposure'),
            'line1': parsed.get('tle1', ''),
            'line2': parsed.get('tle2', ''),
            'sp3_file': parsed.get('sp3_file', '').strip(),
            'sp3_sat_id': parsed.get('sp3_sat_id', '').strip(),
            'reference_image': parsed.get('reference_image', '').strip(),
            'magnitude': to_float('magnitude', -3.5),
            'mag_range': (mag_min, mag_max),
            'mag_back': to_float('mag_back', 16.0),
            'tracking_mode': parsed.get('mode', 'sidereal').strip(),
            'ra_sigma': 0,
            'dec_sigma': 0,
            'shape': to_tuple('ccd_x', 'ccd_y'),
            'fov': to_float('fov'),
            'rotation': to_float('rotation'),
            'cd': (
                [[float(parsed['ccd1_1']), float(parsed['ccd1_2'])],
                [float(parsed['ccd2_1']), float(parsed['ccd2_2'])]]
                if all(parsed.get(k, '').strip() != '' for k in ['ccd1_1', 'ccd1_2', 'ccd2_1', 'ccd2_2'])
                else None
            ),
            'dx': to_float('ccd_y') / 2 + 0.5,
            'dy': to_float('ccd_x') / 2 + 0.5,
            'eA': 0,
            'eD': 0,
            'zero_point': to_float('zero_point'),
            'K': to_float('K'),
            'gain': to_float('gain'),
            'read_noise': to_float('read_noise', 0.0),      
            'dark_current': to_float('dark_current', 0.0),  
            'plate_const': [],
            'inter': True,
            'pixel_size': to_float('pixel_size'),
            'pixel_scale': to_float('pixel_scale'),
            'seeing': to_float('seeing', 1.2),
            'time_init': f"{parsed['year']}-{parsed['month'].zfill(2)}-{parsed['day'].zfill(2)}T"
                         f"{parsed['hour'].zfill(2)}:{parsed['minute'].zfill(2)}:{parsed['second'].zfill(2)}",
            'bias': to_float('bias'),
            'flat': to_float('flat'),
            'output': parsed.get('output', '').strip(),
            'output_name': parsed.get('output_name', 'final_image.png').strip(),
            'add_frame': parsed.get('add_frame', 'False').strip().lower() == 'true',
            'frame_color': parsed.get('frame_color', '#FF0000').strip(),
            'stellarium_scripts_path': parsed.get('stellarium_scripts_path', '').strip()
        }
