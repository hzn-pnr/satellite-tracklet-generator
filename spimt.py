"""
spimt.py
A python code for simulating photometric images of moving target with photon-mapping.
Author: Junju Du
E-mail: dujunju@mail.sdu.edu.cn
Last update: 2021-03-03

This module is based on the original `spimt.py` implementation from SPIMT:
"Simulating Photometric Images of Moving Targets with Photon-Mapping"

Original author: Junju Du
Original repository: https://github.com/Dujunju/SPIMT

The original implementation has been modified and extended by Pınar Hazan
as part of the MSc thesis:

"Optical Tracklet Simulation for Space Surveillance and Tracking"

Modifications and extensions include:

* integration with the broader satellite tracklet simulation workflow;
* support for SP3-based satellite position data;
* additional coordinate and time transformation functions;
* FITS/WCS-related extensions;
* additional functions for automated image and tracklet generation.

The original authorship is retained. The modifications made for this thesis
are identified in the source code where applicable.

Original code copyright remains with the original author.
Modifications copyright (c) 2026 Pınar Hazan.
"""

import math
from abc import ABC
import numpy as np
import numpy.random as rd
import pandas as pd
from pandas import DataFrame
from skyfield.api import Topos, EarthSatellite, load
from astroquery.vizier import Vizier
from astropy.coordinates import SkyCoord
import astropy.units as u
import astropy.io.fits as fits
from astropy.time import Time, TimeDelta
from scipy import interpolate
from astroquery.xmatch import XMatch


from astropy.coordinates import Angle, ITRS, GCRS, CartesianRepresentation, EarthLocation, AltAz
from astropy.utils.iers import conf as iers_conf
from sp3_interpolator import interpolate_over_exposure_tai
from sp3_interpolator import interpolate_over_exposure_tai, interpolate_arbitrary_times_tai, itrf_series_to_gcrs_radec, itrf_series_to_topocentric_radec

iers_conf.auto_download = True  # GCRS conversions may require access to IERS tables.
ts = load.timescale()

# Based on Hazan (2026), p. 59, Eq. (3.30) and Eq. (3.31)
def compute_cd_matrix(pixel_scale_arcsec, rotation_deg, parity=-1):
    scale_deg = pixel_scale_arcsec / 3600.0
    theta = np.deg2rad(-rotation_deg)  # East of North (clockwise) → -rotation
    cd = scale_deg * np.array([
        [-np.cos(theta), np.sin(theta)],
        [-np.sin(theta), -np.cos(theta)]
    ])
    return parity * cd


class Station(Topos):
    """
    A ground station class.
    """
    def __init__(self, *args, **kwargs):
        """
        :param args: the arguments of skyfield.api.Topos.
        :param kwargs: the keywords of skyfield.api.Topos.
        """
        super(Station, self).__init__(*args, **kwargs)


class Target(EarthSatellite):
    """
    A moving target class.
    """
    def __init__(self, *args, magnitude=15, **kwargs):
        """
        :param args: the arguments of skyfield.api.EarthSatellite.
        :param magnitude: the standard magnitude of the moving target.
        :param kwargs: the keywords of skyfield.api.EarthSatellite.
        """
        super(Target, self).__init__(*args, **kwargs)
        self.magnitude = magnitude


# ---------------------- SP3 ----------------------
# Added by Hazan (2026)
def _to_time_utc(t):
    if isinstance(t, Time):
        return t if t.scale == "utc" else t.utc
    return Time(t, scale="utc")

def _skyfield_time_from_astropy(T: Time):
    dt = T.to_datetime()
    return ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                  dt.second + dt.microsecond/1e6)

# Added based on Hazan (2026), p. 56, Eq. (3.26) and Eq. (3.27)
class Sp3Target:
    """
    Target using SP3.
    Usage:
        sat = Sp3Target(sp3_path, "L39", magnitude=15)
        diff = sat - station              # station: Topos (Station) or (lat,lon,elev)
        ra_deg, dec_deg, range_m = diff.at_sp3(t)  # GCRS topocentric
    """
    def __init__(self, sp3_path: str, sat_id: str, *,
                 magnitude: float = 15.0,
                 n_before: int = 5, n_after: int = 5, k_points: int = 10,
                 reference: str = "first",
                 _bound_station=None):
        self.sp3_path = sp3_path
        self.sat_id = sat_id.strip().upper()
        self.magnitude = magnitude
        self.n_before = n_before
        self.n_after = n_after
        self.k_points = k_points
        self.reference = reference
        self._bound_station = _bound_station 

    def __sub__(self, station_obj):
        return Sp3Target(self.sp3_path, self.sat_id,
                         magnitude=self.magnitude,
                         n_before=self.n_before, n_after=self.n_after,
                         k_points=self.k_points, reference=self.reference,
                         _bound_station=station_obj)

    # --- satellite ITRF(ECEF) (m) ---
    def _sat_itrs_xyz_m(self, T: Time) -> np.ndarray:
        rows = interpolate_over_exposure_tai(
            sp3_path=self.sp3_path,
            target_sat_id=self.sat_id,
            start_dt=T.to_datetime(),   # UTC->TAI 
            exposure_seconds=0,
            step_seconds=1,
            n_before=self.n_before, n_after=self.n_after,
            k_points=self.k_points, reference=self.reference
        )
        if not rows:
            raise RuntimeError("SP3 interpolation returned empty rows. Check sat_id/time.")
        _, x_km, y_km, z_km = rows[0]
        return 1e3 * np.array([x_km, y_km, z_km], dtype=float)

  
    def at_sp3(self, t) -> tuple[float, float, float]:
        """
        Bağlı istasyon yoksa → (RA°, Dec°, |r|) jeosantrik,
        varsa → (RA°, Dec°, |LOS|) toposentrik (GCRS).
        """
        T = _to_time_utc(t)

        # Satellite: SP3→ITRF→GCRS
        sat_itrs = self._sat_itrs_xyz_m(T)
        g_sat = ITRS(CartesianRepresentation(*sat_itrs * u.m), obstime=T).transform_to(GCRS(obstime=T))
        sat_gcrs = np.array([g_sat.cartesian.x.to_value(u.m),
                             g_sat.cartesian.y.to_value(u.m),
                             g_sat.cartesian.z.to_value(u.m)], dtype=float)

        if self._bound_station is None:
            los = sat_gcrs
        else:
            st = self._bound_station
            # Skyfield Topos → .at(t)
            if hasattr(st, "at"):
                sf_t = _skyfield_time_from_astropy(T)
                geo = st.at(sf_t)  # Geocentric (ICRF≈GCRS)
                x_km, y_km, z_km = geo.position.km
                sta_gcrs = 1e3 * np.array([x_km, y_km, z_km], dtype=float)
            # (lat, lon, elev)
            elif isinstance(st, (tuple, list)) and len(st) == 3:
                lat_deg, lon_deg, elev_m = float(st[0]), float(st[1]), float(st[2])
                loc = EarthLocation.from_geodetic(lon=lon_deg * u.deg,
                                                  lat=lat_deg * u.deg,
                                                  height=elev_m * u.m)
                itrs = loc.get_itrs(obstime=T)
                g = itrs.transform_to(GCRS(obstime=T))
                sta_gcrs = np.array([g.cartesian.x.to_value(u.m),
                                     g.cartesian.y.to_value(u.m),
                                     g.cartesian.z.to_value(u.m)], dtype=float)
            else:
                raise TypeError("Unsupported station type for Sp3Target.")
            los = sat_gcrs - sta_gcrs

        dist = float(np.linalg.norm(los))
        g_vec = GCRS(CartesianRepresentation(*los * u.m), obstime=T)
        sph = g_vec.spherical
        ra_deg = float(Angle(sph.lon).to_value(u.deg))
        dec_deg = float(Angle(sph.lat).to_value(u.deg))
        return ra_deg, dec_deg, dist, los

    def at_sp3_series(self, times_astropy: Time):
        """
        It takes a time object array and returns RA, Dec as a vector.
        """
        # Get the satellite's ITRF positions (meters) as vectors.
        xyz_km = interpolate_arbitrary_times_tai(
            self.sp3_path, self.sat_id, times_astropy,
            n_before=self.n_before, n_after=self.n_after, 
            k_points=self.k_points, reference=self.reference
        )
        if len(xyz_km) == 0:
            return np.array([]), np.array([])
        
        xyz_m = xyz_km * 1000.0

        # Coordinate transformation (Geocentric or Topocentric)
        if self._bound_station is None:
            # Geocentric RA/Dec
            out = itrf_series_to_gcrs_radec(xyz_m, times_astropy, return_distance=False)
            return out["ra_deg"], out["dec_deg"]
        else:
            # Topocentric RA/Dec
            st = self._bound_station
            lat, lon, h = 0.0, 0.0, 0.0
            
            # Extract station features
            if hasattr(st, "latitude"):
                try: lat = st.latitude.degrees
                except: lat = np.degrees(st.latitude.radians)
                try: lon = st.longitude.degrees
                except: lon = np.degrees(st.longitude.radians)
                try: h = st.elevation.m
                except: h = 0.0
            elif isinstance(st, (tuple, list)) and len(st) >= 2:
                lat = float(st[0])
                lon = float(st[1])
                h = float(st[2]) if len(st) > 2 else 0.0
            
            out = itrf_series_to_topocentric_radec(
                xyz_m, times_astropy,
                station_lat_deg=lat, station_lon_deg=lon, station_h_m=h,
                return_distance=False
            )
            return out["ra_deg"], out["dec_deg"]

class Stars(DataFrame, ABC):
    """
    Field stars class.
    """
    def __init__(self, *args, **kwargs):
        """
        :param args: the arguments of the pandas.DataFrame.
        :param kwargs: the keywords of the pandas.DataFrame.
        """
        super(Stars, self).__init__(*args, **kwargs)


class Telescope:
    """
    A telescope class.
    """
    def __init__(self, ra_sigma=0.02, dec_sigma=0.02, fov=0.2, zero_point=2.4, k=0.17):
        """
        :param ra_sigma: the scale parameter of Brownian motion in right ascension, in pixel/second.
        :param dec_sigma: the scale parameter of Brownian motion in declination, in pixel/second.
        :param fov: the field of view of telescope, in degree.
        :param zero_point: the zero-point of telescope.
        :param k: the first order extinction coefficient.
        """
        self.ra_sigma = ra_sigma
        self.dec_sigma = dec_sigma
        self.fov = fov * u.deg
        self.zero_point = zero_point
        self.k = k


class CCD:
    """
    A CCD class.
    """
    def __init__(self, shape=(2048, 2048), gain=1.63, plate_const=None, cd=None, pixel_size=0.3533, pixel_scale=1):
        """
        :param shape: the dimensions of the CCD.
        :param gain: the gain of the CCD.
        :param plate_const: the plate constants of the CCD.
        :param cd: the WCS (CD1_1, CD1_2, CD2_1, CD2_2) of the CCD.
        :param pixel_size: the pixel size of the CCD.
        :param pixel_scale: the pixel scale of the CCD.
        """
        self.shape = shape
        self.gain = gain
        self.plate_const = np.array(plate_const)
        self.cd = cd
        self.pixel_size = pixel_size
        self.pixel_scale = pixel_scale


class SynFits:
    """
    An observation scene.
    """

    def __init__(self, station=None, target=None, telescope=None, ccd=None, stars=None,
                 time_init=None, exposure=None, tracking_mode='target', A0=None, D0=None, eA=0, eD=0,
                 output_path=None, sp3_limit=None):
        """
        :param station: the ground station.
        :param target: the moving target.
        :param telescope: the telescope.
        :param CCD: the CCD.
        :param stars: the field stars.
        :param time_init: the initial time of exposure.
        :param exposure: the exposure time.
        :param tracking_mode: the tracking mode of telescope.
        :param A0: the right ascension of telescope pointing.
        :param D0: the declination of telescope pointing.
        :param eA: the initial error in right ascension of telescope pointing.
        :param eD: the initial error in declination of telescope pointing.
        """
        self.station = station
        self.target = target
        self.telescope = telescope
        self.ccd = ccd
        self.stars = stars
        self.time_init = Time(time_init, scale='utc') if time_init else None
        self.exposure = TimeDelta(exposure, format='sec') if exposure else None
        self.tracking_mode = tracking_mode
        self.station2target = target - station if (target and station) else None
        self.time_mid = time_init + 0.5 * exposure if (time_init and exposure) else None
        self.A0 = A0
        self.D0 = D0
        self.radec_init = None
        self.radec_mid = None
        self.radec_end = None
        self.eA = eA
        self.eD = eD
        self.output_path = output_path   
        self.comparison_target = None  
        self._is_sp3 = isinstance(self.target, Sp3Target)
        self.sp3_limit = sp3_limit



    def add_station(self, *args, **kwargs):
        """
        Add a ground station to scene.
        :param args: the arguments of Station.
        :param kwargs: the keywords of Station.
        :return:
        """
        print('add station ...')
        self.station = Station(*args, **kwargs)

    def add_target(self, *args, **kwargs):
        """
        Add a moving target to scene.
        :param args: the arguments of Target.
        :param kwargs: the keyword of Target.
        :return:
        """
        print('add target ...')
        self.target = Target(*args, **kwargs)
        self._is_sp3 = False

    # Added by Hazan (2026)
    def add_sp3_target(self, *args, **kwargs):
        """
        SP3 hedef ekle: add_sp3_target(sp3_file=..., sp3_sat_id=..., magnitude=15, ...)
        """
        print('add SP3 target ...')
        sp3_path = kwargs.pop('sp3_file')
        sat_id   = kwargs.pop('sp3_sat_id')
        magnitude = kwargs.pop('magnitude', 15.0)

        self.target = Sp3Target(sp3_path, sat_id, magnitude=magnitude, **kwargs)
        self._is_sp3 = True

        if self.station is not None:
            self.station2target = self.target - self.station


    def add_telescope(self, *args, **kwargs):
        """
        Add a telescope to scene.
        :param args: the arguments of Telescope.
        :param kwargs: the keywords of Telescope.
        :return:
        """
        print('add telescope ...')
        self.telescope = Telescope(*args, **kwargs)

    def add_ccd(self, *args, **kwargs):
        print('add ccd ...')

        if 'cd' not in kwargs or kwargs['cd'] is None:
            if kwargs.get('rotation') not in [None, 0.0] and kwargs.get('pixel_scale') not in [None, 0.0]:
                print('  CD girilmedi, rotation kullanılarak CD matrisi hesaplanıyor...')
                cd = compute_cd_matrix(
                    pixel_scale_arcsec=kwargs['pixel_scale'],
                    rotation_deg=kwargs['rotation'],
                    parity=-1
                )
                kwargs['cd'] = cd
            else:
                raise ValueError("CD matrisi belirtilmedi ve rotation ile pixel_scale de yok. CCD kurulamaz.")

        kwargs.pop('rotation', None)

        self.ccd = CCD(*args, **kwargs)


    def set_setting(self, seeing=2, time_init=None, exposure=None, tracking_mode=None, A0=None, D0=None, eA=0, eD=0):
        """
        Set the observation setting.
        :param seeing: the sigma of PSF. The PSF is a Gaussian function.
        :param time_init: the initial time of exposure.
        :param exposure: the exposure time.
        :param tracking_mode: the tracking mode of telescope.
        :param A0: the right ascension of telescope pointing.
        :param D0: the declination of telescope pointing.
        :param eA: the initial error in right ascension of telescope pointing.
        :param eD: the initial error in declination of telescope pointing.
        :return:
        """
        print('set setting ...')
        self.seeing = seeing
        self.time_init = Time(time_init, scale='utc')
        self.exposure = TimeDelta(exposure, format='sec')
        self.tracking_mode = tracking_mode
        self.time_mid = self.time_init + 0.5 * self.exposure
        self.A0 = A0
        self.D0 = D0
        self.eA = eA
        self.eD = eD

    def add_stars(self, mag_range=None, **kwargs):
        """
        Add field stars to scene.
        :param mag_range: the mag range of field stars.
        :param kwargs:
        :return:
        """
        print('add field stars ...')
        self.station2target = self.target - self.station

        # calculate the mid-exposure (time_mid)，and the corresponding telescope's pointing (A_mid, D_mid).
        if self.tracking_mode == 'target':
            if self._is_sp3:
                A_mid, D_mid, _, _ = self.station2target.at_sp3(self.time_mid)
                A_mid = A_mid + self.eA
                D_mid = D_mid + self.eD
            else:
                A_mid, D_mid, distance = self.station2target.at(ts.from_astropy(self.time_mid)).radec()
                A_mid = A_mid._degrees + self.eA
                D_mid = D_mid._degrees + self.eD
        elif self.tracking_mode == 'sidereal':
            A_mid, D_mid = self.A0, self.D0
        elif self.tracking_mode == 'parking':
            A_mid, D_mid = self.A0 + 15 * 0.5 * self.exposure.value / 3600, self.D0
        else:
            print('The tracking mode can not be recognized!')

        # Obtain the field stars from Vizier.
        # Catalog is 'UCAC4'.
        # fileter is 'V'.
        radec_mid = SkyCoord(A_mid, D_mid, unit=(u.deg, u.deg))
        if self._is_sp3:
            ra0, dec0, _, _ = self.station2target.at_sp3(self.time_init)
            self.radec_init = (ra0, dec0) 
        else:
            self.radec_init = self.station2target.at(ts.from_astropy(self.time_init)).radec()

        self.radec_mid = radec_mid

        custom_visizer = Vizier()
        custom_visizer.ROW_LIMIT = -1
        stars = custom_visizer.query_region(radec_mid, radius=self.telescope.fov / 2, catalog='UCAC4', **kwargs)
        star_df = pd.DataFrame(stars)

        stars = XMatch.query(cat1=stars[0], cat2='vizier:I/350/gaiaedr3', max_distance=1 * u.arcsec, colRA1='RAJ2000',
                             colDec1='DEJ2000')
        stars = stars.to_pandas()
        stars = stars[(stars['Vmag'] > mag_range[0]) & (stars['Vmag'] < mag_range[1])]
        stars['RAJ2000'] = stars['ra'] + stars['pmra'] * (self.time_mid.jyear - 2016) / 1000 / 60 / 60 / np.cos(
            np.deg2rad(stars['dec']))
        stars['DEJ2000'] = stars['dec'] + stars['pmdec'] * (self.time_mid.jyear - 2016) / 1000 / 60 / 60
        stars = stars[['UCAC4', 'RAJ2000', 'DEJ2000', 'Vmag']]
        stars = stars.rename(columns={'UCAC4': 'ID', 'RAJ2000': 'RA', 'DEJ2000': 'DEC', 'Vmag': 'FLUX_V'})
        stars = stars.dropna()

        # Add the target to source list.
        stars = pd.concat([stars, pd.DataFrame([{'FLUX_V': self.target.magnitude, 'ID': 'TARGET'}])], ignore_index=True)


        self.stars = Stars(stars)


    def add_photon(self):
        """
        Add photons from sources to scene.
        Implements Npi and the 1e6 / 10-photon approximation as described in the paper.
        """
        print('add photons ...')
        self.station2target = self.target - self.station

        # The air-mass at mid-exposure.
        if self._is_sp3:
            # Added by Hazan (2026)
            # SP3: RA/Dec → AltAz (Astropy)

            ra_mid, dec_mid, _, _ = self.station2target.at_sp3(self.time_mid)

            # Station → EarthLocation
            try:
                lat_deg = float(self.station.latitude.degrees)
                lon_deg = float(self.station.longitude.degrees)
            except Exception:
                lat_deg = float(self.station.latitude.radians * 180.0 / np.pi)
                lon_deg = float(self.station.longitude.radians * 180.0 / np.pi)
            try:
                elev_m = float(self.station.elevation.m)
            except Exception:
                elev_m = 0.0

            loc = EarthLocation.from_geodetic(lon=lon_deg * u.deg, lat=lat_deg * u.deg, height=elev_m * u.m)
            sc_mid = SkyCoord(ra_mid * u.deg, dec_mid * u.deg, frame='icrs')
            altaz_mid = sc_mid.transform_to(AltAz(obstime=self.time_mid, location=loc))
            alt_rad = float(altaz_mid.alt.to_value(u.rad))   
        else:
            # TLE: Skyfield altaz()
            alt_mid, az_mid, distance_mid = self.station2target.at(ts.from_astropy(self.time_mid)).altaz()
            alt_rad = alt_mid.radians                        

        airmass = 1 / np.cos(0.5 * np.pi - alt_rad)
      

        # FLUX ~ 10^{-0.4(m - ZP + k X(h))}
        # Modified based on Hazan (2026), p. 48, Eq. (3.7) and Eq. (3.8)
        mag_app = self.stars['FLUX_V'] + self.telescope.k * airmass

        self.stars['FLUX'] = 10.0 ** (0.4 * (self.telescope.zero_point - mag_app))

        # ------------------------------
        # LIMIT THE NUMBER OF STARS TO 150.
        # Added based on Hazan (2026), p. 49
        # ------------------------------
        max_stars = 150

        mask_target = self.stars['ID'].astype(str).eq('TARGET')
        stars_df = self.stars.loc[~mask_target].copy()
        target_df = self.stars.loc[mask_target].copy()

        if not stars_df.empty:
            stars_df['LAM_raw'] = stars_df['FLUX'] * self.exposure.value

            # Choose the brightest max_stars star
            if len(stars_df) > max_stars:
                stars_df = stars_df.nlargest(max_stars, 'LAM_raw')

            stars_df = stars_df.drop(columns=['LAM_raw'])

        
        self.stars = pd.concat([stars_df, target_df], ignore_index=True)

        lam = self.stars['FLUX'] * self.exposure.value
        lam = np.nan_to_num(lam, nan=0.0, posinf=1e8, neginf=0.0)
        lam = np.clip(lam, 0, 1e8)

        # Added based on Hazan (2026), p. 50, Eq. (3.12)
        # N_real ~ Poisson(Npi)  (Npi = FLUX * t_exp)
        N_real = np.random.poisson(lam).astype(int)
        self.stars['FLUX_exp'] = N_real 

        print("self.stars", self.stars)

        # If N_real > 1e6 then combine every 10 photons. 
        group_size = 10           # every ten photons are combined into a single entity
        threshold = int(1e6)      # 1,000,000

        N_macro = N_real.copy()   # number of macrophotons to be used for travel-time
        weights = np.ones_like(N_real, dtype=int)  # the weight of each macrophoton

        mask_big = N_real > threshold
        if np.any(mask_big):
            # N_macro = floor(N_real / 10), WEIGHT = 10
            N_macro[mask_big] = (N_real[mask_big] // group_size).astype(int)
         
            N_macro[mask_big] = np.maximum(N_macro[mask_big], 1)
            weights[mask_big] = group_size

        # Generate photon arrival times.
        photons = pd.DataFrame()
        photons['ID'] = self.stars['ID'].values
        photons['N_macro'] = N_macro
        photons['WEIGHT_SRC'] = weights

        # N_macro arrival times for each resource (between 0 and t_exp)
        photons['T_IJ'] = photons['N_macro'].map(
            lambda n: np.random.uniform(0, self.exposure.value, n) if n > 0 else np.array([], dtype=float)
        )

        # Combine the T_IJ sequences
        if len(photons['T_IJ']) > 0:
            t_arrays = photons['T_IJ'].values
            if any(len(a) > 0 for a in t_arrays):
                t_concat = np.concatenate(t_arrays)
            else:
                t_concat = np.array([], dtype=float)
        else:
            t_concat = np.array([], dtype=float)

    
        lengths = photons['T_IJ'].str.len()

        self.photons = pd.DataFrame({
            'ID': photons['ID'].repeat(lengths).values,
            'T_IJ': t_concat,
            'WEIGHT': photons['WEIGHT_SRC'].repeat(lengths).values
        })

        print(self.photons)

        # -------------------------------------------------
        # LIMIT THE TOTAL NUMBER OF PHOTONS GLOBALLY.
        # Added based on Hazan (2026), p. 50, Eq. (3.14) and Eq. (3.15)
        # -------------------------------------------------
        N_total = len(self.photons)
        N_max   = 1_000_000  # Upper limit for total macrophotons.

        if N_total > N_max:
            factor = N_total / float(N_max)

            # Enlarge the weight of each photon to represent more actual photons
            self.photons['WEIGHT'] = self.photons['WEIGHT'] * factor

            
            step = int(np.ceil(factor))
            if step > 1:
                self.photons = self.photons.iloc[::step].reset_index(drop=True)

    

            
    def tracking(self, inter=True):

        """
        Photon tracing.
        :param inter: If interpolate the tracking path or not.
        :return:
        """
        print('tracking ... ')
        photons = self.photons.sort_values(by='T_IJ')
        
        # Brownian motion
        photons['DT'] = photons['T_IJ'].diff().fillna(0)
        photons['DRA'] = np.random.normal(0, photons['DT']**0.5) * self.telescope.ra_sigma
        photons['DDEC'] = np.random.normal(0, photons['DT']**0.5) * self.telescope.dec_sigma
        photons.iloc[0, photons.columns.get_loc('DRA')] = self.eA
        photons.iloc[0, photons.columns.get_loc('DDEC')] = self.eD
        photons['DRA_CUM'] = photons['DRA'].cumsum()
        photons['DDEC_CUM'] = photons['DDEC'].cumsum()

        # Added by Hazan (2026.
        def _get_radec_arrays(times_astropy):
            """Yardımcı fonksiyon: SP3 ise vektörize çağır, değilse Skyfield kullan"""
            if self._is_sp3:
                return self.station2target.at_sp3_series(times_astropy)
            else:
                t = ts.from_astropy(times_astropy)
                ra, dec, _ = self.station2target.at(t).radec()
                return ra._degrees, dec._degrees

        if self.tracking_mode == 'target':
            if inter:
                t_arr = np.arange(0, self.exposure.value + 0.1, 0.1)
                t_astropy = self.time_init + TimeDelta(t_arr, format='sec')
                
                RA_deg, Dec_deg = _get_radec_arrays(t_astropy)
                
                RA_Tar = interpolate.splev(photons['T_IJ'], interpolate.splrep(t_arr, RA_deg, s=0))
                Dec_Tar = interpolate.splev(photons['T_IJ'], interpolate.splrep(t_arr, Dec_deg, s=0))
            else:
                t_vals = photons['T_IJ'].values
                t_astropy = self.time_init + TimeDelta(t_vals, format='sec')
                
                RA_Tar, Dec_Tar = _get_radec_arrays(t_astropy)

            photons['RA_TAR'] = RA_Tar
            photons['DEC_TAR'] = Dec_Tar
            photons['A'] = photons['RA_TAR'] + photons['DRA_CUM']
            photons['D'] = photons['DEC_TAR'] + photons['DDEC_CUM']

        elif self.tracking_mode == 'sidereal':
            mask_tgt = photons['ID'] == 'TARGET'
            t_vals = photons.loc[mask_tgt, 'T_IJ'].values
            if len(t_vals) > 0:
                t_astropy = self.time_init + TimeDelta(t_vals, format='sec')
                ra_arr, dec_arr = _get_radec_arrays(t_astropy)
                
                photons['RA_TAR'] = 0.0; photons['DEC_TAR'] = 0.0
                photons.loc[mask_tgt, 'RA_TAR'] = ra_arr
                photons.loc[mask_tgt, 'DEC_TAR'] = dec_arr
            
            photons['A'] = self.A0 + photons['DRA_CUM']
            photons['D'] = self.D0 + photons['DDEC_CUM']

        elif self.tracking_mode == 'parking':
            mask_tgt = photons['ID'] == 'TARGET'
            t_vals = photons.loc[mask_tgt, 'T_IJ'].values
            if len(t_vals) > 0:
                t_astropy = self.time_init + TimeDelta(t_vals, format='sec')
                ra_arr, dec_arr = _get_radec_arrays(t_astropy)
                photons['RA_TAR'] = 0.0; photons['DEC_TAR'] = 0.0
                photons.loc[mask_tgt, 'RA_TAR'] = ra_arr
                photons.loc[mask_tgt, 'DEC_TAR'] = dec_arr

            photons['A'] = self.A0 + 15 * photons['T_IJ'] / 3600 + photons['DRA_CUM']
            photons['D'] = self.D0 + photons['DDEC_CUM']

        # Photon mapping
        photon_map = pd.merge(self.stars[['RA', 'DEC', 'ID']], photons, on='ID')
        photon_map['RA'] = np.where(photon_map['ID'] == 'TARGET', photon_map['RA_TAR'], photon_map['RA'])
        photon_map['DEC'] = np.where(photon_map['ID'] == 'TARGET', photon_map['DEC_TAR'], photon_map['DEC'])

        # Standard coordinates
        ra_rad = np.deg2rad(photon_map['RA'] - photon_map['A'])
        dec_rad = np.deg2rad(photon_map['DEC'])
        D_rad = np.deg2rad(photon_map['D'])
        
        sin_dec, cos_dec = np.sin(dec_rad), np.cos(dec_rad)
        sin_D, cos_D = np.sin(D_rad), np.cos(D_rad)
        cos_ra = np.cos(ra_rad)
        sin_ra = np.sin(ra_rad)

        T1 = cos_dec * sin_ra
        T2 = sin_dec * cos_D - cos_dec * sin_D * cos_ra
        T3 = sin_dec * sin_D + cos_dec * cos_D * cos_ra
        
        photon_map['XI'] = T1 / T3
        photon_map['ETA'] = T2 / T3

        xy = np.dot(np.linalg.inv(self.ccd.cd), np.rad2deg(photon_map[['XI', 'ETA']].values.T))
        photon_map['X'] = xy[0, :]
        photon_map['Y'] = xy[1, :]
        photon_map['X_SE'] = photon_map['X'] + rd.normal(0, self.seeing, len(photon_map))
        photon_map['Y_SE'] = photon_map['Y'] + rd.normal(0, self.seeing, len(photon_map))
        
        self.photon_map = photon_map


    def rendering(self, bias=0, flat=1, dx=0, dy=0, mag_back=16, read_noise_amount=0, bias_is_realistic=True, dark_current=0, hot_pixels=False):
        """
        Image rendering.
        :param bias: the bias.
        :param flat: the flat.
        :param dx:
        :param dy:
        :return:
        """
        print('rendering ...')

        img_photon = np.zeros(self.ccd.shape, dtype=float)
        y_size = self.ccd.shape[0]
        x_size = self.ccd.shape[1]

        # Use the WEIGHT column if it exists; otherwise, consider all columns as 1.
        if 'WEIGHT' in self.photon_map.columns:
            weights = self.photon_map['WEIGHT'].to_numpy(dtype=float)
        else:
            weights = np.ones(len(self.photon_map), dtype=float)

        x_arr = self.photon_map['X_SE'].to_numpy(dtype=float)
        y_arr = self.photon_map['Y_SE'].to_numpy(dtype=float)

        # Image plane sampling.
        for x, y, w in zip(x_arr, y_arr, weights):
            x = x + dx
            y = y + dy

            if (-0.5 < x < x_size) and (-0.5 < y < y_size):
                # For normal sources, w = 1
                # For resources where N_real > 1e6, w = 10
                # Added Based on Hazan (2026), p. 50
                img_photon[int(y), int(x)] += w

        self.img_photon = img_photon
    
        # BIAS 
        # Added based on Hazan (2026), p. 63
        bias_im = np.zeros(self.ccd.shape) + bias

        if bias_is_realistic and bias > 0:
            rng_bias = np.random.RandomState(seed=8392)        
            number_of_columns = 5
            shape = self.ccd.shape
            
            # Select random columns
            columns = rng_bias.randint(0, shape[1], size=number_of_columns)
            
            # Set a variation limit of 10% of the bias.
            limit = int(0.1 * bias)
            if limit < 1: limit = 1 
            
            col_pattern = rng_bias.randint(0, limit, size=shape[0])

            # Make the selected columns a little brighter.
            for c in columns:
                bias_im[:, c] = bias + col_pattern


        # DARK CURRENT & HOT PIXELS 
        # Added based on Hazan (2026), p. 64
        dark_im_adu = np.zeros(self.ccd.shape)
        
        if dark_current > 0:
            base_current_adu = dark_current * self.exposure.value / self.ccd.gain
            
            # Poisson noise
            dark_im_adu = np.random.poisson(base_current_adu, size=self.ccd.shape).astype(float)
            
            # Hot Pixels 
            if hot_pixels:
                y_max, x_max = self.ccd.shape
                # 0.01% hot pixels
                n_hot = int(0.0001 * x_max * y_max)
                
                rng_hot = np.random.RandomState(16201649)
                hot_x = rng_hot.randint(0, x_max, size=n_hot)
                hot_y = rng_hot.randint(0, y_max, size=n_hot)
                
                # 10,000 times the normal current.
                hot_current_val = 10000 * dark_current
                
                # Convert to ADU and add  it to the image.
                hot_val_adu = hot_current_val * self.exposure.value / self.ccd.gain
                dark_im_adu[(hot_y, hot_x)] = hot_val_adu


        # READ NOISE
        # Added based on Hazan (2026), p. 64
        if read_noise_amount > 0:
            noise_adu = rd.normal(scale=read_noise_amount / self.ccd.gain, size=self.ccd.shape)
        else:
            noise_adu = 0.0

        # Added based on Hazan (2026), p. 61
        if mag_back == 0:
            self.image_adu = (img_photon / self.ccd.gain) * flat + dark_im_adu + bias_im + noise_adu
        else:
            N = 10.0 ** (0.4 * (self.telescope.zero_point - mag_back)) * self.exposure.value
            
            # Sky background shot noise (Poisson)
            background_e = np.random.poisson(N, size=self.ccd.shape)

            # Modifid based on Hazan (2026), p. 66, Eq. (3.35)
            self.image_adu = ((img_photon + background_e) / self.ccd.gain) * flat + dark_im_adu + bias_im + noise_adu



    def writeto(self, img_photon='photon.fits', img_adu='adu.fits', header=None, **kwargs):
        """
        write the image ti fits file.
        :param img_photon: the file name of image in photon-electrons.
        :param img_adu: the file name of image in ADU.
        :param header: the header of fits file.
        :param kwargs: keywords of fits.PrimaryHDU.writeto.
        :return:
        """
        print('write to ...')

        hdu = fits.PrimaryHDU(self.img_photon.astype(np.float32), header=header)
        hdu.writeto(img_photon, **kwargs)

        hdu = fits.PrimaryHDU(self.image_adu.astype(np.float32), header=header)
        hdu.writeto(img_adu, **kwargs)



if __name__ == '__main__':
    pass





