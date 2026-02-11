from sklearn.ensemble import RandomForestRegressor
import pandas as pd

class DigitalTwinModel:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, max_depth=15, n_jobs=-1)
        self.is_trained = False
        self.features = ['virtual_power', 'speed_mps', 'dist', 'temp', 'ele', 'hum'] # wind_speed_mps and wind_dir implicitly included via virtual_power

    def train(self, df_history):
        """
        Trains the Digital Twin model to predict heart rate from physics and environment
        """
        numeric_cols = df_history.select_dtypes(include=['number']).columns
        if 'hr' not in numeric_cols: raise KeyError("Missing numeric 'hr'")
        
        if 'hum' not in df_history.columns:
            df_history['hum'] = 50.0
        
        df_clean = df_history.dropna(subset=self.features + ['hr'])
        
        df_resampled = df_clean.iloc[::30] # Downsample to every 30th second
        
        X = df_resampled[self.features]
        y = df_resampled['hr']
        
        self.model.fit(X, y)
        self.is_trained = True
        return self.model.score(X, y)

    def predict_drift(self, df_new):
        """
        Calculates the physiological drift (Actual HR - Predicted HR)
        """
        if not self.is_trained: raise Exception("Model not trained.")
        
        X = df_new[self.features].fillna(0) # Fill missing for prediction
        df_new = df_new.copy()
        
        df_new['hr_predicted'] = self.model.predict(X) # Save predicted HR (i.e., what should be the HR based on physics/speed)
        
        # Calculate drift:
        # Positive drift (+10) = heart is beating faster than expected (e.g., heat, tired/fatigue)
        # Negative drift (-10) = heart is beating slower (e.g., fresh, cold)
        df_new['drift'] = df_new['hr'] - df_new['hr_predicted']
        
        return df_new

    def analyze_influence(self, df_new):
        """
        Analyzes the environmental influence on heart rate by comparing
        """
        if not self.is_trained: raise Exception("Model not trained.")
        
        # 1. Predict HR under actual conditions
        X_actual = df_new[self.features].fillna(0)
        hr_actual_pred = self.model.predict(X_actual)
        
        # 2. Predict HR under standard conditions -> counterfactual
        X_standard = X_actual.copy()
        X_standard['temp'] = 20.0  # Default temp
        X_standard['hum'] = 40.0   # Default humidity
        X_standard['ele'] = 100.0  # Sea level
        
        hr_standard_pred = self.model.predict(X_standard)
        
        # 3. Calculate deltas
        df_new['hr_predicted'] = hr_actual_pred # Save for drift calc
        df_new['env_penalty_bpm'] = hr_actual_pred - hr_standard_pred
        df_new['drift'] = df_new['hr'] - df_new['hr_predicted']
        
        return df_new
