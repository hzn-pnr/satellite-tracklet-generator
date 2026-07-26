# tle_fetcher.py
"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com
"""

import requests
import datetime
import urllib.parse
import configparser
import os
import json
import time
from typing import List, Tuple, Optional

# --- Configuration Loading ---
config = configparser.ConfigParser()
config.read('config.ini')

try:
    USERNAME = config['spacetrack']['username']
    PASSWORD = config['spacetrack']['password']
except KeyError:
    raise KeyError("Could not find 'username' or 'password' in config.ini under the [spacetrack] section.")

BASE_URL = "https://www.space-track.org"
LOGIN_URL = f"{BASE_URL}/ajaxauth/login"
CACHE_FILE = "satcat_cache.json"  
CACHE_EXPIRY_HOURS = 24  # How long should the catalog be valid for? (Space-Track rule: minimum 24 hours)

class SpaceTrackClient:
    """
    A client to interact with the Space-Track.org API.
    Handles login and data fetching for satellite catalogs and TLEs using the new GP API.
    """
    def __init__(self, identity: str, password: str):
        self.session = requests.Session()
        self.identity = identity
        self.password = password
        self.logged_in = False

    def _ensure_login(self):
        """
        Logs in only if not already logged in.
        """
        if not self.logged_in:
            login_data = {'identity': self.identity, 'password': self.password}
            print("Logging in to Space-Track...")
            login_response = self.session.post(LOGIN_URL, data=login_data)
            
            if login_response.status_code != 200:
                raise Exception(f"Login failed with status {login_response.status_code}. Check credentials.")
            
            self.logged_in = True
            print("Login successful.")

    def fetch_satellite_catalog(self) -> List[str]:
        """
        Fetches the complete public satellite catalog.
        CACHING IMPLEMENTED: Checks for a local file first. If it's newer than 24 hours,
        it uses the local file to prevent API bans.
        """
        
        if self._is_cache_valid():
            print(f"Using cached satellite catalog from '{CACHE_FILE}' (no API call made).")
            return self._load_cache()

        
        self._ensure_login()
        
       
        catalog_url = (
            f"{BASE_URL}/basicspacedata/query/class/satcat/"
            "orderby/NORAD_CAT_ID asc/format/csv"
        )
        print("Fetching full satellite catalog from API (this may take a moment)...")
        response = self.session.get(catalog_url)
        
        if response.status_code != 200:
           
            if os.path.exists(CACHE_FILE):
                print(f"API failed ({response.status_code}), falling back to expired cache.")
                return self._load_cache()
            raise Exception(f"Catalog fetch failed: {response.status_code} - {response.text}")

        lines = response.text.splitlines()
        if not lines:
            return []

        header = lines[0].split(",")
        try:
            idx_name = header.index("OBJECT_NAME")
        except ValueError:
            raise ValueError("Could not find 'OBJECT_NAME' column in the catalog CSV.")

        names = [line.split(",")[idx_name].strip('" ') for line in lines[1:] if line.strip()]
        unique_names = sorted(set(names))
        
        print(f"Fetched {len(unique_names)} unique satellites. Saving to cache...")
        self._save_cache(unique_names)
        
        return unique_names

    def _is_cache_valid(self) -> bool:
        """Checks if the cache file exists and is less than CACHE_EXPIRY_HOURS old."""
        if not os.path.exists(CACHE_FILE):
            return False
        
        file_mod_time = os.path.getmtime(CACHE_FILE)
        current_time = time.time()
        hours_diff = (current_time - file_mod_time) / 3600
        
        if hours_diff < CACHE_EXPIRY_HOURS:
            return True
        else:
            print(f"Cache expired (Age: {hours_diff:.1f} hours).")
            return False

    def _load_cache(self) -> List[str]:
        """Loads satellite names from JSON cache."""
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)

    def _save_cache(self, data: List[str]):
        """Saves satellite names to JSON cache."""
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f)

    def get_closest_tle(self, name_or_norad: str, target_date_iso: str, search_window_days: int = 5) -> Optional[Tuple[str, str]]:
        """
        Finds the TLE for a satellite closest to a specific target date.
        UPDATED: Uses 'gp_history' class instead of deprecated 'tle' class.
        """
        self._ensure_login()

        try:
            target_date = datetime.datetime.fromisoformat(target_date_iso)
        except ValueError:
            raise ValueError("Invalid target_date_iso format. Please use 'YYYY-MM-DD'.")

        start_date = (target_date - datetime.timedelta(days=search_window_days)).strftime("%Y-%m-%d")
        end_date = (target_date + datetime.timedelta(days=search_window_days)).strftime("%Y-%m-%d")

      
        if name_or_norad.strip().isdigit():
            search_field = f"norad_cat_id/{name_or_norad}"
        else:
            search_field = f"OBJECT_NAME/{urllib.parse.quote(name_or_norad.strip())}"

       
        query_url = (
            f"{BASE_URL}/basicspacedata/query/class/gp_history/"
            f"{search_field}/"
            f"EPOCH/{start_date}--{end_date}/"
            f"orderby/epoch desc/format/tle"
        )

        response = self.session.get(query_url)
        
        if response.status_code == 429:
            print("Warning: Rate limit exceeded (429). You are querying too fast.")
            return None
        elif response.status_code != 200:
            print(f"Warning: TLE query failed with status {response.status_code}")
            return None

        tle_lines = response.text.strip().splitlines()
        if len(tle_lines) < 2:
            print(f"No TLE data found for '{name_or_norad}' in the specified date range.")
            return None

        best_pair = None
        min_diff = datetime.timedelta.max

        for i in range(0, len(tle_lines), 2):
            if i+1 >= len(tle_lines): break
            line1 = tle_lines[i]
            line2 = tle_lines[i+1]
            
            try:
                parts = line1.split()
                epoch_str = parts[3] 
                year_short = int(epoch_str[:2])
               
                year = 1900 + year_short if year_short >= 57 else 2000 + year_short
                
                day_of_year_fraction = float(epoch_str[2:])
                epoch_date = datetime.datetime(year, 1, 1) + datetime.timedelta(days=day_of_year_fraction - 1)
                
                diff = abs(epoch_date - target_date)
                if diff < min_diff:
                    min_diff = diff
                    best_pair = (line1, line2)
            except Exception:
                continue

        return best_pair

