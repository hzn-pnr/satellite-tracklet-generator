"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com
"""

import spimt as psim


def img_generator(Ps):

    cb = Ps.get('progress_callback')
    def report_progress(val):
        if cb:
            cb(int(val))
    # --------------------------------------

    stop_checker = Ps.get('check_stop_func')
    def check_stop():
        if stop_checker:
            stop_checker()

    check_stop()
    report_progress(5)

    # Initialize a scene.
    a_fits = psim.SynFits()
    a_fits.time_sampler = 'grid'
    MANUEL_SP3_LIMIT = 100_000_000
    a_fits = psim.SynFits(sp3_limit=MANUEL_SP3_LIMIT)

    # Add a ground station.
    a_fits.add_station(
        latitude_degrees=Ps['latitude'],
        longitude_degrees=Ps['longitude'],
        elevation_m=Ps['elevation'])
    
    check_stop()
    report_progress(10)

    # Add a moving target: choose between TLE vs SP3 from Ps
    line1 = (Ps.get('line1') or '').strip()
    line2 = (Ps.get('line2') or '').strip()
    sp3_file = (Ps.get('sp3_file') or '').strip()
    sp3_sat_id = (Ps.get('sp3_sat_id') or '').strip()

    tle_ok = bool(line1 and line2)
    sp3_ok = bool(sp3_file and sp3_sat_id)

    if not tle_ok and not sp3_ok:
            raise ValueError("At least one orbit source must be specified...")

    if tle_ok:
        print("Target set as TLE.")
        a_fits.add_target(line1, line2, magnitude=Ps['magnitude'])
    elif sp3_ok:
        print("Target set as SP3.")
        a_fits.add_sp3_target(
            sp3_file=sp3_file,
            sp3_sat_id=sp3_sat_id,
            magnitude=Ps['magnitude']
        )

    check_stop()
    report_progress(20)
    # Add a telescope.
    a_fits.add_telescope(
        ra_sigma=Ps['ra_sigma'],
        dec_sigma=Ps['dec_sigma'],
        fov=Ps['fov'],
        zero_point=Ps['zero_point'],
        k=Ps['K'])

    # Add a CCD.
    a_fits.add_ccd(
        shape=Ps['shape'],
        gain=Ps['gain'],
        plate_const=Ps['plate_const'],
        rotation=Ps.get('rotation', 0.0),
        cd=Ps.get('cd', None),
        pixel_size=Ps['pixel_size'],
        pixel_scale=Ps['pixel_scale'])
    
    check_stop()
    report_progress(30)

    # Set the observation setting.
    a_fits.set_setting(
        seeing=Ps['seeing'],
        time_init=Ps['time_init'],
        exposure=Ps['exposure'],
        tracking_mode=Ps['tracking_mode'],
        A0=Ps['A0'],
        D0=Ps['D0'],
        eA=Ps['eA'],
        eD=Ps['eD'])

    check_stop()
    report_progress(35)
    # Add field stars.
    a_fits.add_stars(mag_range=Ps['mag_range'])

    check_stop()
    report_progress(50)

    # Add photons.
    a_fits.add_photon()
    check_stop()
    report_progress(60)

    # Photon tracing.
    a_fits.tracking(inter=Ps['inter'])
    check_stop()
    report_progress(80)

    # Image rendering.
    a_fits.rendering(
        bias=Ps['bias'],
        dx=Ps['dx'],
        dy=Ps['dy'],
        mag_back=Ps.get('mag_back', 16),
        read_noise_amount=Ps.get('read_noise', 0),
        dark_current=Ps.get('dark_current', 0))
    

    check_stop()
    report_progress(95)

    # Write image to fits file.
    a_fits.writeto(
        img_photon=Ps['img_photo'],
        img_adu=Ps['img_adu'],
        overwrite=True)
    
    report_progress(100)
    