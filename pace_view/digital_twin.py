"""
Random-forest based digital twin for physiological response modeling.
"""

from sklearn.ensemble import RandomForestRegressor
import numpy as np

class DigitalTwinModel:
    """
    Fits a digital twin that predicts heart rate from physics and environment.
    """
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, max_depth=15, n_jobs=-1, random_state=0)
        self.is_trained = False
        # wind_speed_mps and wind_dir are implicitly included via virtual_power
        self.features = ["virtual_power", "speed_mps", "dist", "temp", "ele", "hum"]

    def train(self, df_history):
        """
        Trains the Digital Twin model to predict heart rate from physics and environment.
        """
        numeric_cols = df_history.select_dtypes(include=["number"]).columns
        if "hr" not in numeric_cols:
            raise KeyError("Missing numeric 'hr'")

        if "hum" not in df_history.columns:
            df_history["hum"] = 50.0

        df_clean = df_history.dropna(subset=self.features + ["hr"])
        
        if "weather_imputed" in df_clean.columns:
            if df_clean["weather_imputed"].all():
                # no observed weather, i.e., temp/hum are constant, so their effect cannot be learned
                self.features = [f for f in self.features if f not in ("temp", "hum")]
                print("No observed weather in training data: temperature/humidity are not used.")
            else:
                # skip placeholder weather
                df_clean = df_clean[~df_clean["weather_imputed"].astype(bool)]

        df_resampled = df_clean.iloc[::30]  # Downsample to every 30th second

        X = df_resampled[self.features]
        y = df_resampled["hr"]

        self.model.fit(X, y)
        self.is_trained = True
        return self.model.score(X, y)

    def evaluate(self, df_history, group_col="ride_id"):
        """
        Leave-one-ride-out evaluation: for each ride, train on all other rides and test on it.
        Call after train(). Baseline = mean heart rate of the training rides.
        """
        from sklearn.base import clone
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        df = df_history.dropna(subset=self.features + ["hr"])
        if "weather_imputed" in df.columns and any(f in self.features for f in ("temp", "hum")):
            df = df[~df["weather_imputed"].astype(bool)]
        ys, preds, bases = [], [], []
        for ride in df[group_col].unique():
            train, test = df[df[group_col] != ride].iloc[::30], df[df[group_col] == ride]
            model = clone(self.model).fit(train[self.features], train["hr"])
            ys.append(test["hr"].to_numpy())
            preds.append(model.predict(test[self.features]))
            bases.append(np.full(len(test), train["hr"].mean()))
        y, p, b = np.concatenate(ys), np.concatenate(preds), np.concatenate(bases)
        return {
            "n_rides": len(ys),
            "mae": mean_absolute_error(y, p),
            "rmse": mean_squared_error(y, p) ** 0.5,
            "r2": r2_score(y, p),
            "baseline_mae": mean_absolute_error(y, b),
        }

    def predict(self, df_new):
        """
        Predicts heart rate for the provided dataframe.
        """
        if not self.is_trained:
            raise Exception("Model not trained.")
        X = df_new[self.features].fillna(0)
        return self.model.predict(X)

    def predict_drift(self, df_new):
        """
        Calculates the physiological drift (Actual HR - Predicted HR).
        """
        if not self.is_trained:
            raise Exception("Model not trained.")

        df_new = df_new.copy()
        df_new["hr_predicted"] = self.predict(df_new)

        # Positive drift (+10) = heart is beating faster than expected (e.g., heat, fatigue)
        # Negative drift (-10) = heart is beating slower (e.g., fresh, cold)
        df_new["drift"] = df_new["hr"] - df_new["hr_predicted"]

        return df_new
