import os
import pandas as pd
import numpy as np
from sport_activities_features.tcx_manipulation import TCXFile
from sport_activities_features import WeatherIdentification
from .mining import PatternMiner
from .physics import PhysicsEngine
from .learning import DigitalTwinModel

class ContextTrainer:
    def __init__(self, history_folder, weather_api_key=None, time_delta=1):
        self.history_folder = history_folder
        self.api_key = weather_api_key
        self.time_delta = time_delta
        self.tcx_loader = TCXFile()
        self.miner = PatternMiner()
        self.engine = PhysicsEngine()
        self.model = DigitalTwinModel()

    def _get_val(self, item, keys):
        for k in keys:
            if isinstance(item, dict):
                if k in item: return item[k]
            else:
                if hasattr(item, k): return getattr(item, k)
        return 0.0

    def _process_file(self, filepath, is_training=False):
        """
        Ports a TCX file into a DataFrame with physics and weather data (using Visual Crossing API)
        """
        try:
            raw = self.tcx_loader.read_one_file(filepath)
            act = self.tcx_loader.extract_activity_data(raw, numpy_array=True)
            if 'Biking' not in act.get('activity_type', ''):
                return None
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return None
        
        weather_data = []
        if self.api_key and not is_training:
            try:
                wid = WeatherIdentification(act['positions'], act['timestamps'], self.api_key)
                w_list = wid.get_weather(time_delta=self.time_delta)
                weather_data = wid.get_average_weather_data(act['timestamps'], w_list)
            except Exception as e:
                print(f"Weather API Error: {e}. Using Neutral weather.")
                weather_data = [{'temp': 20, 'wspd': 0, 'wdir': 0, 'hum': 20}] * len(act['timestamps'])
        else:
            weather_data = [{'temp': 20, 'wspd': 0, 'wdir': 0, 'hum': 20}] * len(act['timestamps'])

        temps = [self._get_val(w, ['temp', 'temperature']) for w in weather_data]
        hums = [self._get_val(w, ['hum', 'humidity']) for w in weather_data]
        winds = [self._get_val(w, ['wspd', 'wind_speed']) for w in weather_data]
        bearings = [self._get_val(w, ['wdir', 'wind_direction']) for w in weather_data]

        hr_numeric = pd.to_numeric(act['heartrates'], errors='coerce')
        speed_numeric = pd.to_numeric(act['speeds'], errors='coerce')
        min_len = min(len(act['timestamps']), len(hr_numeric))

        df = pd.DataFrame({
            'time': act['timestamps'][:min_len],
            'lat': [p[0] for p in act['positions']][:min_len],
            'lon': [p[1] for p in act['positions']][:min_len],
            'ele': act['altitudes'][:min_len],
            'dist': act['distances'][:min_len],
            'hr': hr_numeric[:min_len],
            'speed_mps': speed_numeric[:min_len] / 3.6,
            'temp': temps[:min_len],
            'wind_speed_mps': np.array(winds[:min_len]) / 3.6,
            'wind_dir': bearings[:min_len],
            'hum': hums[:min_len]
        })

        return self.engine.calculate_virtual_power(df)

    def fit(self):
        """
        Creates and trains the Digital Twin model from historical data
        """
        print(f"Loading history from {self.history_folder}...")
        files = [f for f in os.listdir(self.history_folder) if f.endswith('.tcx')]
        dfs = []
        for i, f in enumerate(files):
            try:
                path = os.path.join(self.history_folder, f)
                df = self._process_file(path, is_training=True)
                if df is not None and len(df) > 0:
                    dfs.append(df)
                if i % 10 == 0: print(f"  Processed {i}/{len(files)} activities...")
            except: pass 

        if not dfs: raise Exception("No valid TCX files found.")

        print("Training Physiological Model...")
        full_history = pd.concat(dfs, ignore_index=True)
        score = self.model.train(full_history)
        print(f"Model Trained! Accuracy (R2): {score:.2f}")
        
        print("Caching history for pattern mining...")
        
        full_history_analyzed = self.model.predict_drift(full_history) # Add 'drift' column to history (for miner)
        
        cache_path = os.path.join(self.history_folder, "history_cache.csv") # Save cached history for pattern mining
        full_history_analyzed.to_csv(cache_path, index=False)
        print(f"History cache saved to: {cache_path}")

    def mine_patterns(self):
        """
        Uses Nature-Inspired Algorithms to find global rules about the athlete
        """
        cache_path = os.path.join(self.history_folder, "history_cache.csv")
        
        if not os.path.exists(cache_path):
            print("No history cache found. Please run .fit() first.")
            return

        print(f"Loading history from {cache_path}...")
        df_history = pd.read_csv(cache_path)
        
        rules = self.miner.discover_rules(df_history) # Run NiaARM
        
        print("Discovered Athlete Rules (Nature-Inspired):")
        if not rules:
            print("No strong patterns found yet. Need more data.")
        else:
            for i, rule in enumerate(rules[:5]): 
                print(f"{i+1}. {rule}")

    def explain(self, tcx_filepath):
        """
        Explain a new activity file with contextual intelligence using the trained model (Digital Twin using Random Forest Regressor)
        """
        print(f"Analyzing {tcx_filepath}...")
        
        df = self._process_file(tcx_filepath, is_training=False)
        df = self.model.analyze_influence(df)

        rationales = {}

        # 1. Wind rationale (impact distribution)
        minutes_in_headwind = len(df[df['headwind_mps'] > 3.0]) / 60 # Count minutes spent in significant headwind (> 3 m/s)
        total_minutes = len(df) / 60
        pct_headwind = (minutes_in_headwind / total_minutes) * 100 if total_minutes > 0 else 0

        if pct_headwind > 25:
             rationales['Wind'] = f"NEGATIVE: Battled Headwinds for {minutes_in_headwind:.0f} mins ({pct_headwind:.0f}% of ride)."
        elif pct_headwind < 5 and df['headwind_mps'].mean() < -1:
             rationales['Wind'] = "ASSISTED: Mostly tailwinds."
        else:
             rationales['Wind'] = "NEUTRAL: Mostly calm winds."

        # 2. Grativity rationale (mechanical)
        minutes_climbing = len(df[df['grad'] > 0.03]) / 60 # Count significant climbing time (> 3% grade)
        if minutes_climbing > 20:
            rationales['Terrain'] = f"HIGH RESISTANCE: {minutes_climbing:.0f} mins of steep climbing."
        else:
            rationales['Terrain'] = "NEUTRAL: Terrain was mostly flat/rolling."

        # 3. Thermal rationale (physiological)
        avg_thermal_penalty = df['env_penalty_bpm'].mean() # Average HR penalty due to temp/humidity
        if avg_thermal_penalty > 3:
            rationales['Atmosphere'] = f"HEAT STRESS: High Temp/Humidity raised HR by {avg_thermal_penalty:.1f} bpm."
        elif avg_thermal_penalty < -3:
            rationales['Atmosphere'] = f"COOLING EFFECT: Low Temps lowered HR by {abs(avg_thermal_penalty):.1f} bpm."
        else:
            rationales['Atmosphere'] = "NEUTRAL: Optimal temperatures."

        insight = {
            "Analysis": "Contextual Intelligence Report",
            "Summary_Metrics": {
                "Avg_Speed": f"{df['speed_mps'].mean() * 3.6:.1f} km/h",
                "Avg_Power": f"{df['virtual_power'].mean():.0f} W",
                "Avg_HR": f"{df['hr'].mean():.0f} bpm",
                "Avg_Temp": f"{df['temp'].mean():.1f} °C"
            },
            "Rationales": rationales,
            "Conclusion": self._generate_conclusion(rationales)
        }
            
        return insight

    def _generate_conclusion(self, rationales):
        """
        Generates a textual conclusion based on rationales
        """
        factors = []
        for k, v in rationales.items():
            if "NEGATIVE" in v or "HIGH" in v or "STRESS" in v:
                factors.append(v)
        if not factors:
            return "Perfect Conditions. Performance reflects raw fitness."
        return " | ".join(factors)
