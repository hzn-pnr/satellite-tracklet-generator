# sp3_interpolator.py
"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com
"""

from datetime import datetime
from typing import Dict, Tuple, List
import numpy as np
from astropy.time import Time, TimeDelta
from astropy import units as u
from astropy.coordinates import ITRS, GCRS, CartesianRepresentation, EarthLocation, Angle
from astropy.utils.iers import conf as iers_conf

from sp3_parser import parse_sp3_and_get_neighbors

iers_conf.auto_download = True


# Based on Hazan (2026), p. 56, Eq. (3.26) and Eq. (3.27)
def _lagrange_scalar(eph_scalar: float, dat: np.ndarray) -> float:
    t_vals = dat[:, 1]
    if len(np.unique(t_vals)) != len(t_vals):
        raise ValueError("For Lagrangian, t-values ​​must be unique.")

    total = 0.0
    N = dat.shape[0]
    for i in range(N):
        Li = 1.0
        ti = dat[i, 1]
        for j in range(N):
            if j == i: continue
            tj = dat[j, 1]
            Li *= (eph_scalar - tj) / (ti - tj)
        total += Li * dat[i, 0]
    return float(total)

def cal_sp3(eph_scalar: float, sp3_mat: np.ndarray) -> np.ndarray:
    if sp3_mat.ndim != 2 or sp3_mat.shape[1] != 4:
        raise ValueError("sp3_mat must have the shape (N, 4): [x, y, z, t].")
    x = sp3_mat[:, 0]
    y = sp3_mat[:, 1]
    z = sp3_mat[:, 2]
    t = sp3_mat[:, 3]

    info_x = np.column_stack([x, t])
    info_y = np.column_stack([y, t])
    info_z = np.column_stack([z, t])

    x_last = _lagrange_scalar(eph_scalar, info_x)
    y_last = _lagrange_scalar(eph_scalar, info_y)
    z_last = _lagrange_scalar(eph_scalar, info_z)

    return np.array([x_last, y_last, z_last], dtype=float)



def _lagrange_vectorized(eph_scalars: np.ndarray, dat: np.ndarray) -> np.ndarray:
    """
    Vectorized Lagrangian interpolation.
    eph_scalars: Time series of dimension (M,) (target moments)
    dat: Nodes of dimension (N, 2) [value, time]
    return: Interpolated values ​​of dimension (M,).
    """
    t_vals = dat[:, 1]
    vals = dat[:, 0]
    N = len(t_vals)
    M = len(eph_scalars)
    
    total = np.zeros(M, dtype=float)
    
    # Calculate Lagrangian basis polynomials as vectors.
    for i in range(N):
        Li = np.ones(M, dtype=float)
        ti = t_vals[i]
        val_i = vals[i]
        for j in range(N):
            if i == j:
                continue
            tj = t_vals[j]
            Li *= (eph_scalars - tj) / (ti - tj)
        total += Li * val_i
        
    return total

def cal_sp3_vectorized(eph_scalars: np.ndarray, sp3_mat: np.ndarray) -> np.ndarray:
    """
    Vectorized SP3 calculation.
    eph_scalars: (M,) second offsets
    sp3_mat: (N, 4) constant adjacency matrix [x, y, z, t]
    Return: (M, 3) -> [[x0, y0, z0], ...]
    """
    x = sp3_mat[:, 0]
    y = sp3_mat[:, 1]
    z = sp3_mat[:, 2]
    t = sp3_mat[:, 3]
    
    info_x = np.column_stack([x, t])
    info_y = np.column_stack([y, t])
    info_z = np.column_stack([z, t])
    
    # Vector interpolation for each axis
    x_vec = _lagrange_vectorized(eph_scalars, info_x)
    y_vec = _lagrange_vectorized(eph_scalars, info_y)
    z_vec = _lagrange_vectorized(eph_scalars, info_z)
    
    return np.column_stack([x_vec, y_vec, z_vec])

def interpolate_arbitrary_times_tai(
    sp3_path: str,
    target_sat_id: str,
    times_astropy: Time, 
    n_before: int = 5,
    n_after: int = 5,
    k_points: int = 10,
    reference: str = "first"
) -> np.ndarray:
    """
    SP3 interpolates an arbitrary time sequence (vector). It reads the file ONLY ONCE (for the midpoint) and uses those neighbors for all points. 
    Assumption: The times in 'times_astropy' are spread over a short interval (e.g., a exposure duration).
    """
    if len(times_astropy) == 0:
        return np.array([])

    # Convert all times to TAI scale (vector)
    t_tai = times_astropy.tai
    
    # Find the midpoint in terms of reference time
    # This time determines which 10(k) neighbors will be pulled from the file.
    min_mjd = np.min(t_tai.mjd)
    max_mjd = np.max(t_tai.mjd)
    mid_mjd = (min_mjd + max_mjd) / 2.0
    
    center_tai = Time(mid_mjd, format='mjd', scale='tai')
    center_dt = center_tai.to_datetime() 

    # Read the neighbors from the SP3 file.
    parsed = parse_sp3_and_get_neighbors(
        sp3_path=sp3_path,
        target_dt=center_dt,
        n_before=n_before,
        n_after=n_after,
        target_sat_id=target_sat_id
    )
    
    sp3_mat, _, epochs = build_sp3_matrix_from_parser_result(parsed, reference=reference)

    # Calculate scalar offsets (vector) for all time periods.
    t0_tai = Time(epochs[0], scale='tai')
    if reference == "target":
         # If reference='target', the target time we give to the parser is considered 0.
         t_ref_tai = Time(parsed["meta"]["requested_target"], scale='tai')
    else:
         t_ref_tai = t0_tai
    
    # Second difference
    eph_scalars = (t_tai - t_ref_tai).to_value('sec')
    
    # Choose the most suitable k points for interpolation.    
    mean_scalar = np.mean(eph_scalars)
    subset = select_k_nearest(sp3_mat, eph_scalar=mean_scalar, k=k_points)
    
    # Vectorized calculation
    xyz_m = cal_sp3_vectorized(eph_scalars, subset) # km 
    
    return xyz_m # (M, 3) km



def build_sp3_matrix_from_parser_result(parser_result: Dict, reference: str = "first") -> Tuple[np.ndarray, float, List[datetime]]:
    nodes = parser_result["nodes"]
    if not nodes:
        raise ValueError("Parser result is empty.")
    items = sorted(nodes.items(), key=lambda kv: kv[0])
    epochs = [ep for ep, _ in items]
    coords = [xyz for _, xyz in items]

    if reference == "first":
        t_ref = epochs[0]
    elif reference == "target":
        t_ref = parser_result["meta"]["requested_target"]
    else:
        raise ValueError("The reference should be either 'first' or 'target'.")

    t_secs = np.array([(ep - t_ref).total_seconds() for ep in epochs], dtype=float)
    xyz = np.array(coords, dtype=float)
    sp3_mat = np.column_stack([xyz, t_secs])
    return sp3_mat, 0.0, epochs

def select_k_nearest(sp3_mat: np.ndarray, eph_scalar: float, k: int = 10) -> np.ndarray:
    if sp3_mat.shape[0] <= k:
        subset = sp3_mat.copy()
    else:
        idx = np.argsort(np.abs(sp3_mat[:, 3] - eph_scalar))[:k]
        subset = sp3_mat[idx]
    subset = subset[np.argsort(subset[:, 3])]
    return subset

def interpolate_over_exposure_tai(sp3_path: str, target_sat_id: str, start_dt: datetime, exposure_seconds: int, step_seconds: int = 1, n_before: int = 5, n_after: int = 5, k_points: int = 10, reference: str = "first") -> List[Tuple[datetime, float, float, float]]:
    start_tai = Time(start_dt, scale="utc").tai
    start_tai_dt = start_tai.to_datetime()
    parsed = parse_sp3_and_get_neighbors(sp3_path, start_tai_dt, n_before, n_after, target_sat_id)
    sp3_mat, _, epochs = build_sp3_matrix_from_parser_result(parsed, reference=reference)
    
    t0_tai = Time(epochs[0], scale="tai")
    if reference == "target":
        target_tai = Time(parsed["meta"]["requested_target"], scale="tai")

    results = []
    num_steps = exposure_seconds // step_seconds
    for k in range(num_steps + 1):
        t_eval_tai = start_tai + TimeDelta(k * step_seconds, format="sec")
        if reference == "first":
            eph_scalar = (t_eval_tai - t0_tai).to_value("sec")
        else:
            eph_scalar = (t_eval_tai - target_tai).to_value("sec")
        subset = select_k_nearest(sp3_mat, eph_scalar=eph_scalar, k=k_points)
        x_km, y_km, z_km = cal_sp3(eph_scalar, subset)
        t_eval_utc = t_eval_tai.utc.to_datetime()
        results.append((t_eval_utc, x_km, y_km, z_km))
    return results

# --- COORDINATE TRANSFORMS (VECTORIZED) ---

def itrf_series_to_gcrs_radec(xyz_m, times, *, return_distance=True):
    xyz_m = np.asarray(xyz_m, dtype=float)
    T = times if isinstance(times, Time) else Time(times, scale="utc")
    if T.isscalar:
        T = Time(np.repeat(T.datetime, xyz_m.shape[0]), scale=T.scale)

    x, y, z = xyz_m[:, 0]*u.m, xyz_m[:, 1]*u.m, xyz_m[:, 2]*u.m
    itrs = ITRS(CartesianRepresentation(x, y, z), obstime=T)
    gcrs = itrs.transform_to(GCRS(obstime=T))

    sph = gcrs.spherical
    ra_deg  = Angle(sph.lon).to_value(u.deg)
    dec_deg = Angle(sph.lat).to_value(u.deg)

    out = {
        "gcrs_xyz_m": np.column_stack([gcrs.cartesian.x.value, gcrs.cartesian.y.value, gcrs.cartesian.z.value]),
        "ra_deg": np.asarray(ra_deg, dtype=float),
        "dec_deg": np.asarray(dec_deg, dtype=float),
    }
    if return_distance:
        out["distance_m"] = sph.distance.to_value(u.m)
    return out

def itrf_series_to_topocentric_radec(sat_xyz_m, times, station_lat_deg, station_lon_deg, station_h_m=0.0, *, return_distance=True):
    sat_xyz_m = np.asarray(sat_xyz_m, dtype=float)
    T = times if isinstance(times, Time) else Time(times, scale="utc")
    if T.isscalar:
        T = Time(np.repeat(T.datetime, sat_xyz_m.shape[0]), scale=T.scale)

    loc = EarthLocation.from_geodetic(lon=station_lon_deg*u.deg, lat=station_lat_deg*u.deg, height=station_h_m*u.m)
    sta_itrs = loc.get_itrs(obstime=T)
    sta_xyz_m = np.column_stack([sta_itrs.cartesian.x.to_value(u.m), sta_itrs.cartesian.y.to_value(u.m), sta_itrs.cartesian.z.to_value(u.m)])

    los_itrs_m = sat_xyz_m - sta_xyz_m
    los_itrs = ITRS(CartesianRepresentation(los_itrs_m[:,0]*u.m, los_itrs_m[:,1]*u.m, los_itrs_m[:,2]*u.m), obstime=T)
    los_gcrs = los_itrs.transform_to(GCRS(obstime=T))

    sph = los_gcrs.spherical
    out = {
        "ra_deg": np.asarray(Angle(sph.lon).to_value(u.deg), dtype=float),
        "dec_deg": np.asarray(Angle(sph.lat).to_value(u.deg), dtype=float),
    }
    if return_distance:
        out["distance_m"] = sph.distance.to_value(u.m)
    return out