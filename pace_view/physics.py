import numpy as np
import pandas as pd

class PhysicsEngine:
    def __init__(self, rider_mass=75, bike_mass=10):
        self.mass = rider_mass + bike_mass
        self.g = 9.81
        self.rho = 1.225
        self.cd_a = 0.32

    def calculate_virtual_power(self, df):
        """
        Calculates the virtual power required based on physics model.
        """
        # 1. Use vectorized calculations for headwind and bearing
        df['prev_lat'] = df['lat'].shift(1)
        df['prev_lon'] = df['lon'].shift(1)
        
        lat1, lon1, lat2, lon2 = map(np.radians, [df['prev_lat'], df['prev_lon'], df['lat'], df['lon']])
        d_lon = lon2 - lon1
        x = np.sin(d_lon) * np.cos(lat2)
        y = np.cos(lat1) * np.sin(lat2) - (np.sin(lat1) * np.cos(lat2) * np.cos(d_lon))
        bearing = (np.degrees(np.arctan2(x, y)) + 360) % 360
        df['bearing'] = bearing.bfill()

        wind_rad = np.radians(df['wind_dir'] - df['bearing'])
        df['headwind_mps'] = df['wind_speed_mps'] * np.cos(wind_rad)

        # 2. Physics model (smooth elevation first for gradient calculation)
        df['ele_smooth'] = df['ele'].rolling(window=10, min_periods=1).mean()

        df['grad'] = df['ele_smooth'].diff() / df['dist'].diff()
        df['grad'] = df['grad'].fillna(0).clip(-0.25, 0.25)
        
        airspeed = df['speed_mps'] + df['headwind_mps'] # Effective airspeed
        p_aero = 0.5 * self.rho * self.cd_a * (airspeed**2) * df['speed_mps'] # Aerodynamic power
        
        p_grav = self.mass * self.g * np.sin(np.arctan(df['grad'])) * df['speed_mps'] # Gravitational power
        
        p_roll = self.mass * self.g * 0.005 * np.cos(np.arctan(df['grad'])) * df['speed_mps'] # Rolling resistance coefficient
        
        df['p_aero'] = p_aero
        df['p_grav'] = p_grav
        df['p_roll'] = p_roll
        
        df['virtual_power'] = (p_aero + p_grav + p_roll).clip(lower=0) # Total virtual power
        
        return df
