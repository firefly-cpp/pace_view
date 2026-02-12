"""
Cleaning and alignment logic for parsed activity and weather data.
"""

from dataclasses import dataclass
import numpy as np
import pandas as pd
import plotly.express as plotlyy


@dataclass
class AthleteConfig:
    h_r_max: int = 190
    h_r_rest: int = 55
    h_r_r_bound = (0.5, 0.6, 0.7, 0.8, 0.9, 1.1)
    coefficient = (1, 2, 3, 4, 5)
    b: float = 1.92


class DataCleaner:
    """
    Builds a clean, aligned dataframe from parsed TCX and weather data.
    """
    def __init__(self, parser=None):
        self.parser = parser

    def to_dataframe(self, act, weather_data):
        """
        Clean and align parsed activity + weather into a dataframe.
        """
        if self.parser is None:
            raise ValueError("DataCleaner requires a DataParser instance for weather-aligned dataframes.")
        temps = [self.parser._get_val(w, ["temp", "temperature"]) for w in weather_data]
        hums = [self.parser._get_val(w, ["hum", "humidity"]) for w in weather_data]
        winds = [self.parser._get_val(w, ["wspd", "wind_speed"]) for w in weather_data]
        bearings = [self.parser._get_val(w, ["wdir", "wind_direction"]) for w in weather_data]

        hr_numeric = pd.to_numeric(act["heartrates"], errors="coerce")
        speed_numeric = pd.to_numeric(act["speeds"], errors="coerce")
        min_len = min(len(act["timestamps"]), len(hr_numeric))

        df = pd.DataFrame(
            {
                "time": act["timestamps"][:min_len],
                "lat": [p[0] for p in act["positions"]][:min_len],
                "lon": [p[1] for p in act["positions"]][:min_len],
                "ele": act["altitudes"][:min_len],
                "dist": act["distances"][:min_len],
                "hr": hr_numeric[:min_len],
                "speed_mps": speed_numeric[:min_len] / 3.6,
                "temp": temps[:min_len],
                "wind_speed_mps": np.array(winds[:min_len]) / 3.6,
                "wind_dir": bearings[:min_len],
                "hum": hums[:min_len],
            }
        )

        return df

    def get_calory_average(self, exercises):
        """
        Calculate average calories across exercises.
        """
        calories = [e.calories for (_, e) in exercises]
        if not calories:
            return 0.0
        return float(np.average(calories))

    def exercises_to_df(self, exercises):
        """
        Convert tcxreader exercises into a summary dataframe.
        """
        columns = [
            "activity_type",
            "start_time",
            "end_time",
            "calories",
            "avg_speed",
            "duration",
            "distance",
            "altitude_avg",
        ]
        df = pd.DataFrame([{f: getattr(e, f) for f in columns} for (_, e) in exercises])
        return df

    def get_exercise_dataframe(self, exercises):
        """
        Return a cleaned summary dataframe with ISO year-week labels.
        """
        df = self.exercises_to_df(exercises)
        df["start_time"] = pd.to_datetime(df["start_time"])
        df["end_time"] = pd.to_datetime(df["end_time"])

        df = df.dropna(subset=["start_time", "end_time"], how="all")
        iso = df["start_time"].dt.isocalendar()
        df["iso_year_week"] = iso["year"].astype(str) + "" + iso["week"].astype(str).str.zfill(2)
        return df

    def exercise_timeframes(self, exercise):
        """
        Convert a tcxreader exercise into a clean time-series dataframe.
        """
        rows = []
        if exercise.trackpoints:
            for tp in exercise.trackpoints:
                rows.append(
                    {
                        "time": pd.to_datetime(tp.time, utc=True, errors="coerce"),
                        "h_r": tp.hr_value,
                        "dist_m": tp.distance,
                        "alt_m": tp.elevation,
                        "lat": tp.latitude,
                        "lon": tp.longitude,
                    }
                )

            df = pd.DataFrame(rows).dropna(subset=["time"]).sort_values("time").drop_duplicates("time")
            for c in ["h_r", "dist_m", "alt_m", "lat", "lon"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            df["dt_s"] = df["time"].diff().dt.total_seconds().clip(lower=0)
            df["speed_mps"] = df["dist_m"].diff() / df["dt_s"].replace(0, np.nan)
            return df.reset_index(drop=True)
        return None

    def hrr_intensity(self, h_r: pd.Series, config: AthleteConfig) -> pd.Series:
        return (h_r - config.h_r_rest) / (config.h_r_max - config.h_r_rest)

    def assign_zones_hrr(self, h_r: pd.Series, config: AthleteConfig) -> pd.Series:
        x = self.hrr_intensity(h_r, config).clip(lower=0, upper=1.2)
        bounds = np.array(config.h_r_r_bound)
        z = np.digitize(x, bounds, right=True).clip(1, 5)
        return pd.Series(z, index=h_r.index)

    def time_in_zones(self, df: pd.DataFrame, config: AthleteConfig) -> dict:
        z = self.assign_zones_hrr(df["h_r"], config)
        return {f"z{k}_sec": float(df.loc[z == k, "dt_s"].sum()) for k in range(1, 6)}

    def bannister_trimp(self, df: pd.DataFrame, cfg: AthleteConfig) -> float:
        dt_min = (df["dt_s"] / 60.0).fillna(0)
        hrr = self.hrr_intensity(df["h_r"].astype(float), cfg).clip(lower=0, upper=1.2)
        return float((dt_min * hrr * np.exp(cfg.b * hrr)).sum())

    def edwards_trimp(self, df: pd.DataFrame, cfg: AthleteConfig) -> float:
        z = self.assign_zones_hrr(df["h_r"], cfg)
        total = 0.0
        for k, coeff in enumerate(cfg.coefficient, start=1):
            minutes = df.loc[z == k, "dt_s"].sum() / 60.0
            total += coeff * minutes
        return float(total)

    def summarize_exercise(self, df_ex: pd.DataFrame, config: AthleteConfig) -> dict:
        start = df_ex["time"].iloc[0]
        duration_s = float(df_ex["dt_s"].sum())

        if df_ex["dist_m"].notna().any():
            dist_m = float(df_ex["dist_m"].iloc[-1] - df_ex["dist_m"].iloc[0])
            dist_km = dist_m / 1000.0
        else:
            dist_km = np.nan

        zones = self.time_in_zones(df_ex, config)

        return {
            "date": start.tz_convert(None).date(),
            "start_time": start,
            "duration_s": duration_s,
            "distance_km": dist_km,
            "avg_h_r": float(df_ex["h_r"].mean(skipna=True)),
            "avg_speed_mps": float(df_ex["speed_mps"].mean(skipna=True)),
            "trimp_bannister": self.bannister_trimp(df_ex, config),
            "trimp_edwards": self.edwards_trimp(df_ex, config),
            **zones,
        }

    def exercise_summaries(self, exercises, config=None) -> pd.DataFrame:
        summaries = []
        cfg = config or AthleteConfig()
        for (_, exercise) in exercises:
            if exercise.activity_type == "Biking":
                df_exer = self.exercise_timeframes(exercise)
                if df_exer is not None:
                    dict_exer = self.summarize_exercise(df_exer, cfg)
                    if dict_exer:
                        summaries.append(dict_exer)
        return pd.DataFrame(summaries).sort_values("start_time")

    def hr_zones_summary(self, total_summary: pd.DataFrame, period: str) -> pd.DataFrame:
        df = total_summary.copy()
        df["date"] = pd.to_datetime(df["date"])
        max_date = df["date"].max()

        start = max_date - pd.to_timedelta(period)

        zone_cols = [f"z{i}_sec" for i in range(1, 6)]
        sums = df.loc[df["date"] >= start, zone_cols].sum()

        out = sums.rename_axis("category").reset_index(name="value")

        return out

    def ewma_series(self, daily: pd.Series, tau_days: int) -> pd.Series:
        """
        Exponentially weighted moving average helper.
        """
        alpha = 2 / (tau_days + 1)
        return daily.ewm(alpha=alpha, adjust=False).mean()

    def build_dashboard(self, exercises):
        """
        Build the dashboard summary dataframe from tcxreader exercises.
        """
        total_summary = self.exercise_summaries(exercises)

        if total_summary.empty:
            raise ValueError("No usable trackpoints found in given TCX files.")

        total_summary.dropna()

        total_summary["week"] = pd.to_datetime(total_summary["date"]).dt.to_period("W").astype(str)
        total_summary["date"] = pd.to_datetime(total_summary["date"])
        total_summary["speed_kmh"] = total_summary["avg_speed_mps"] * 3.6
        total_summary["duration_min"] = total_summary["duration_s"] / 60
        total_summary["month"] = total_summary["date"].dt.to_period("M").astype(str)
        total_summary["week"] = total_summary["date"].dt.to_period("W").astype(str)

        daily_load = total_summary.groupby("date")["trimp_bannister"].sum()
        daily_load.index = pd.to_datetime(daily_load.index)
        daily_load = daily_load.asfreq("D", fill_value=0)

        _ = self.ewma_series(daily_load, 42)
        _ = self.ewma_series(daily_load, 7)

        return total_summary

    def return_figures(self, total_summary: pd.DataFrame, period, window_days=90):
        """
        Build plotly figures for the dashboard.
        """
        weekly_z_hours = self.hr_zones_summary(total_summary, period)
        figuero1 = plotlyy.pie(
            weekly_z_hours,
            names="category",
            values="value",
        )

        fig2_df = total_summary.copy()
        fig2_df = fig2_df.dropna(subset=["avg_h_r"])
        fig2_df = fig2_df[fig2_df["speed_kmh"] > 0]
        fig2_df["speed_kmh_per_avg_h_r"] = fig2_df["speed_kmh"].fillna(0).div(fig2_df["avg_h_r"])
        fig2_df = fig2_df.sort_values("date")
        fig2_df["date"] = pd.to_datetime(fig2_df["date"])

        min_points = 2
        x_seconds = fig2_df["date"].astype("int64") / 1e9

        rolling = []

        for i, current_date in enumerate(fig2_df["date"]):
            start_date = current_date - pd.Timedelta(days=window_days)
            truth_condition = (fig2_df["date"] >= start_date) & (fig2_df["date"] <= current_date)
            xs = x_seconds[truth_condition]
            ys = fig2_df.loc[truth_condition, "speed_kmh_per_avg_h_r"]
            if len(xs) >= min_points:
                slope, intercept = np.polyfit(xs, ys, 1)
                rolling.append(slope * x_seconds.iloc[i] + intercept)
            else:
                rolling.append(np.nan)

        figuero2 = plotlyy.scatter(
            fig2_df,
            x="date",
            y="speed_kmh_per_avg_h_r",
        )

        figuero2.add_scatter(
            x=fig2_df["date"],
            y=rolling,
            mode="lines",
            name=f"{window_days}D rolling trend",
        )

        figuero3 = plotlyy.scatter(
            total_summary,
            x="avg_h_r",
            y="speed_kmh",
            color="month",
            trendline="ols",
        )

        speed_bins = np.arange(0, total_summary["speed_kmh"].max() + 3, 3)
        dur_bins = np.arange(0, total_summary["duration_min"].max() + 15, 15)
        total_summary["speed_bin"] = pd.cut(total_summary["speed_kmh"], bins=speed_bins)
        total_summary["dur_bin"] = pd.cut(total_summary["duration_min"], bins=dur_bins)

        hm = (
            total_summary.groupby(["dur_bin", "speed_bin"], observed=True)["avg_h_r"]
            .mean()
            .reset_index()
        )

        hm["speed_mid"] = hm["speed_bin"].apply(lambda x: x.mid)
        hm["dur_mid"] = hm["dur_bin"].apply(lambda x: x.mid)

        figuero4 = plotlyy.density_heatmap(
            hm,
            x="speed_mid",
            y="dur_mid",
            z="avg_h_r",
            histfunc="avg",
            nbinsx=len(speed_bins) - 1,
            nbinsy=len(dur_bins) - 1,
            labels={"speed_mid": "Avg speed (km/h)", "dur_mid": "Duration (min)", "avg_h_r": "Avg HR (bpm)"},
            title="Heatmap: mean HR by speed x duration",
        )

        return figuero1, figuero2, figuero3, figuero4
