"""
Orchestrates the end-to-end contextual intelligence flow for cycling data from TCX files.
"""

import os
import pandas as pd
from .data_parsing import DataParser
from .data_cleaning import DataCleaner
from .physics import PhysicsEngine
from .digital_twin import DigitalTwinModel
from .counterfactual import CounterfactualAnalyzer
from .rationale import RationaleGenerator
from .mining import PatternMiner


class ContextTrainer:
    """
    High-level API that ties parsing, physics, digital twin, and XAI together.
    """
    def __init__(self, history_folder, weather_api_key=None, time_delta=60, physics_params=None):
        self.history_folder = history_folder
        self.parser = DataParser(weather_api_key=weather_api_key, time_delta=time_delta)
        self.cleaner = DataCleaner(self.parser)
        self.engine = PhysicsEngine(**(physics_params or {}))
        self.model = DigitalTwinModel()
        self.counterfactual = CounterfactualAnalyzer(self.model)
        self.rationale = RationaleGenerator()
        self.miner = PatternMiner()

    def _process_file(self, filepath, is_training=False):
        """
        Parse, clean, and enrich a TCX file with physics and weather features.
        """
        parsed = self.parser.parse_file(filepath, is_training=is_training)
        if parsed is None:
            return None

        act, weather_data = parsed
        df = self.cleaner.to_dataframe(act, weather_data)
        df["ride_id"] = os.path.basename(filepath)

        return self.engine.calculate_virtual_power(df)

    def fit(self):
        """
        Train the Digital Twin model on all historical TCX files. This reflects component 2 of the architecture for environmental quantification.
        """
        print(f"Loading history from {self.history_folder}...")
        files = [f for f in os.listdir(self.history_folder) if f.endswith('.tcx')]
        dfs = []
        self.failed_files = []
        for i, f in enumerate(files):
            try:
                path = os.path.join(self.history_folder, f)
                df = self._process_file(path, is_training=True)
                if df is not None and len(df) > 0:
                    dfs.append(df)
                if i % 10 == 0: print(f"  Processed {i}/{len(files)} activities...")
            except Exception as e:
                print(f"  Skipping {f}: {e}")
                self.failed_files.append(f)

        if not dfs: raise Exception("No valid TCX files found.")

        print("Training Physiological Model...")
        full_history = pd.concat(dfs, ignore_index=True)
        score = self.model.train(full_history)
        self.history = full_history
        print(f"Model trained. In-sample R2 (training data, not a validation score): {score:.2f}")
        
        print("Caching history for pattern mining...")
        
        full_history_analyzed = self.model.predict_drift(full_history) # Add 'drift' column to history (for miner)
        
        cache_path = os.path.join(self.history_folder, "history_cache.csv") # Save cached history for pattern mining
        full_history_analyzed.to_csv(cache_path, index=False)
        print(f"History cache saved to: {cache_path}")

    def evaluate(self): return self.model.evaluate(self.history)

    def mine_patterns(self):
        """
        Mine global patterns from cached history and return a report for the dashboard.
        """
        cache_path = os.path.join(self.history_folder, "history_cache.csv")
        
        if not os.path.exists(cache_path):
            print("No history cache found. Please run .fit() first.")
            return

        print(f"Loading history from {cache_path}...")
        df_history = pd.read_csv(cache_path)
        
        report = self.miner.discover_rules(df_history)  # Run NiaARM

        rules = report.get("Top_Rules", []) if isinstance(report, dict) else report

        print("Discovered Athlete Rules (Nature-Inspired):")
        if not rules:
            print("No strong patterns found yet. Need more data.")
        else:
            for i, rule in enumerate(rules[:5]):
                print(f"{i+1}. {rule}")

        return report

    def explain(self, tcx_filepath):
        """
        Generate a counterfactual-based explanation for a new activity file.
        """
        print(f"Analyzing {tcx_filepath}...")

        df = self._process_file(tcx_filepath, is_training=False)
        df = self.counterfactual.analyze(df)

        return self.rationale.build_report(df)
