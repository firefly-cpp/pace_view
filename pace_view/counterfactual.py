"""
Counterfactual analysis for estimating environmental impact on performance.
"""


class CounterfactualAnalyzer:
    """
    Counterfactual analysis using the trained Digital Twin.
    Compares predicted HR under actual vs. standard conditions.
    """

    def __init__(self, model, standard_env=None):
        self.model = model
        self.standard_env = standard_env or {"temp": 20.0, "hum": 40.0, "ele": 100.0}

    def analyze(self, df_new):
        """
        Add counterfactual fields (env_penalty_bpm, drift, hr_predicted) to a ride.
        """
        if not self.model.is_trained:
            raise Exception("Model not trained.")

        df_new = df_new.copy()

        # 1. Predict HR under actual conditions
        X_actual = df_new[self.model.features].fillna(0)
        hr_actual_pred = self.model.model.predict(X_actual)

        # 2. Predict HR under standard conditions -> counterfactual
        X_standard = X_actual.copy()
        for key, value in self.standard_env.items():
            if key in X_standard.columns:
                X_standard[key] = value

        hr_standard_pred = self.model.model.predict(X_standard)

        # 3. Calculate deltas
        df_new["hr_predicted"] = hr_actual_pred

        df_new["env_penalty_bpm"] = hr_actual_pred - hr_standard_pred
        # temperature/humidity part only, so that elevation effects are not reported as weather
        thermal = {k: v for k, v in self.standard_env.items() if k in ("temp", "hum") and k in X_actual.columns}
        weather_missing = "weather_imputed" in df_new.columns and df_new["weather_imputed"].all()
        if thermal and not weather_missing:
            X_thermal = X_actual.copy()
            for key, value in thermal.items():
                X_thermal[key] = value
            df_new["env_penalty_thermal_bpm"] = hr_actual_pred - self.model.model.predict(X_thermal)
        else:
            df_new["env_penalty_thermal_bpm"] = float("nan")

        df_new["drift"] = df_new["hr"] - df_new["hr_predicted"]

        return df_new
