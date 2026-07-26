"""
This file is part of StellariumRC, originally developed by k96e.

Original repository:
https://github.com/k96e/StellariumRC

Original license:
MIT License
Copyright (c) 2023 k96e

This copy is included in the Satellite Tracklet Generator project for
communication with the Stellarium Remote Control API.

See StellariumRC/LICENSE for the full license text.
"""

import requests

class Simbad:
    def __init__(self, ip="127.0.0.1", port=8090, password=""):
        self.ip = ip
        self.port = port
        self.password = password
        
    def lookup(self, keyword):
        """
        Performs a SIMBAD lookup for the string keyword using the Stellarium-configured server 
        and returns the results as a JSON object of format.
        """
        r = requests.get(f"http://{self.ip}:{self.port}/api/simbad/lookup",
                         params={"str":keyword},auth=("",self.password))
        try:
            return r.json()
        except requests.exceptions.JSONDecodeError:
            raise Exception(r.text)
        