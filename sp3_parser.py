# sp3_parser.py

"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, List
import re
import math
import bisect


def parse_epoch_from_star_line(line: str) -> Optional[datetime]:
    """
    Parse lines like: '*  YYYY  M  D HH  mm  ss.sssss'
    Returns a datetime or None if format mismatches.
    """
    parts = line.strip().split()
    if not parts or parts[0] != '*':
        return None
    try:
        year = int(parts[1])
        month = int(parts[2])
        day = int(parts[3])
        hour = int(parts[4])
        minute = int(parts[5])
        sec_float = float(parts[6])
        sec = int(sec_float)
        micro = int(round((sec_float - sec) * 1_000_000))
        return datetime(year, month, day, hour, minute, sec, micro)
    except Exception:
        return None


def extract_epoch_interval_seconds(header_line_2: str) -> Optional[float]:
    """
    SP3 header '##' line: epoch interval in columns 25-38 (1-based).
    Fallback: 3rd numeric in the line.
    """
    if len(header_line_2) >= 38:
        candidate = header_line_2[24:38].strip()
        try:
            return float(candidate)
        except Exception:
            pass

    floats = re.findall(r'[+-]?\d+(?:\.\d+)?', header_line_2)
    if len(floats) >= 3:
        try:
            return float(floats[2])
        except Exception:
            return None
    return None


def parse_position_from_p_line_with_id(line: str) -> Optional[Tuple[str, float, float, float]]:
    """
    Returns rows of type 'PG04 ...' or 'P G04 ...' (row_id='G04', x, y, z). XYZ is read from fixed columns (SP3 fixed width).
    """
    if not line.startswith('P'):
        return None

    parts = line.split()
    sat_id = None

    if len(parts) >= 1 and parts[0].startswith('P') and len(parts[0]) >= 2:
        cand = parts[0][1:4]  # 'G04'
        if cand and cand[0].isalpha():
            sat_id = cand

    if not sat_id:
        raw_id = line[1:4].strip()
        if raw_id:
            sat_id = raw_id

    if not sat_id and len(parts) >= 2:
        sat_id = parts[1]

    if not sat_id:
        return None

    try:
        x = float(line[4:18].strip())
        y = float(line[18:32].strip())
        z = float(line[32:46].strip())
    except Exception:
        return None

    sat_id = sat_id.strip().upper()
    if sat_id.startswith('P'):  # 'PG04' -> 'G04'
        sat_id = sat_id[1:]

    return sat_id, x, y, z


def compute_neighbor_epochs(
    first_epoch: datetime,
    interval_sec: float,
    target_dt: datetime,
    n_before: int = 5,
    n_after: int = 5
) -> List[datetime]:
    """
        For target time target_dt:
        - t_floor = round down target_dt to the interval
        - 'before': n_before items backwards (in ascending order), INCLUDING t_floor
        - 'after': n_after items forwards starting from t_floor + Δ
        """
    step = timedelta(seconds=interval_sec)
    idx_float = (target_dt - first_epoch).total_seconds() / interval_sec
    idx_floor = math.floor(idx_float)

    before_indices = list(range(idx_floor - (n_before - 1), idx_floor + 1))
    after_indices = list(range(idx_floor + 1, idx_floor + 1 + n_after))

    indices = before_indices + after_indices
    return [first_epoch + i * step for i in indices]


def _find_closest_epoch(sorted_epochs: List[datetime], target_ep: datetime, tol_sec: float) -> Optional[datetime]:
    """
    sorted_epochs: artan sıralı gerçek epoch listesi (dosyadan)
    target_ep:     aranan epoch (komşu listeden)
    tol_sec:       zaman toleransı (saniye)
    """
    idx = bisect.bisect_left(sorted_epochs, target_ep)
    candidates = []
    if idx < len(sorted_epochs):
        candidates.append(sorted_epochs[idx])
    if idx > 0:
        candidates.append(sorted_epochs[idx - 1])
    if not candidates:
        return None
    best = min(candidates, key=lambda t: abs((t - target_ep).total_seconds()))
    if abs((best - target_ep).total_seconds()) <= tol_sec:
        return best
    return None


def parse_sp3_and_get_neighbors(
    sp3_path: str,
    target_dt: datetime,
    n_before: int = 5,
    n_after: int = 5,
    target_sat_id: str = "G04"  
) -> Dict:
    """
    Parses the SP3 file and returns (x, y, z) coordinates ONLY for the target_sat_id
    at neighboring epochs around the target time.

    Returns:
      {
        'meta': {
            'epoch_interval_seconds': float,
            'first_epoch': datetime,
            'requested_target': datetime,
            'neighbors_requested': [datetime, ...],
            'sat_id': str
        },
        'nodes': {
            datetime: (x_km, y_km, z_km), ...
        }
      }
    """
    with open(sp3_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()


    header2_line = None
    for ln in lines[:50]:
        if ln.startswith('##'):
            header2_line = ln
            break
    if header2_line is None:
        raise ValueError("Couldn't find '##' header line to extract epoch interval.")

    epoch_interval = extract_epoch_interval_seconds(header_line_2=header2_line)
    if epoch_interval is None:
        raise ValueError("Failed to parse epoch interval from header.")
    # kayan nokta sapmalarını azalt
    epoch_interval = int(round(epoch_interval))


    first_epoch = None
    for ln in lines:
        if ln.startswith('*'):
            dt = parse_epoch_from_star_line(ln)
            if dt is not None:
                first_epoch = dt
                break
    if first_epoch is None:
        raise ValueError("No epoch ('*') line found in SP3.")


    neighbor_epochs = compute_neighbor_epochs(
        first_epoch=first_epoch,
        interval_sec=epoch_interval,
        target_dt=target_dt,
        n_before=n_before,
        n_after=n_after
    )


    TARGET_SAT_ID = target_sat_id.strip().upper()
    if TARGET_SAT_ID.startswith('P'):  # 'PG04' -> 'G04'
        TARGET_SAT_ID = TARGET_SAT_ID[1:]


    epoch_to_xyz: Dict[datetime, Tuple[float, float, float]] = {}
    current_epoch: Optional[datetime] = None

    for ln in lines:
        if ln.startswith('*'):
            current_epoch = parse_epoch_from_star_line(ln)
            continue

        if current_epoch is not None and ln.startswith('P'):
            parsed = parse_position_from_p_line_with_id(ln)
            if parsed is None:
                continue
            sid, x, y, z = parsed
            if sid == TARGET_SAT_ID:
                epoch_to_xyz[current_epoch] = (x, y, z)

  
    sorted_real_epochs = sorted(epoch_to_xyz.keys())
    tol_sec = epoch_interval / 10.0  

    nodes: Dict[datetime, Tuple[float, float, float]] = {}
    for ep in neighbor_epochs:
        match = _find_closest_epoch(sorted_real_epochs, ep, tol_sec)
        if match is not None:
            nodes[ep] = epoch_to_xyz[match]

    return {
        "meta": {
            "epoch_interval_seconds": epoch_interval,
            "first_epoch": first_epoch,
            "requested_target": target_dt,
            "neighbors_requested": neighbor_epochs,
            "sat_id": TARGET_SAT_ID
        },
        "nodes": nodes
    }
