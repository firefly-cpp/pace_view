from tcxreader.tcxreader import TCXReader, TCXExercise
import os
import numpy as np
from collections import defaultdict
from datetime import datetime
import pandas as pd
from dataclasses import dataclass
import matplotlib.pyplot as plt
import time
import plotly.express as plotlyy

@dataclass
class AthleteConfig:
    h_r_max: int = 190
    h_r_rest: int = 55
    h_r_r_bound = (0.5, 0.6, 0.7, 0.8, 0.9, 1.1)
    coefficient = (1, 2, 3, 4, 5)
    b:float = 1.92

READ_LIMIT = 600

class ASTTCXReader:
    def __init__(self, dir_path):
        self.tcx_reader = TCXReader()
        self.dir_path = dir_path
        self.exercises_val = []
        self.__read_from_tcx_files()
    
    def __read_from_tcx_files(self):
        exercise_val = []
        # dir_length = len(os.listdir(self.dir_path))
        for idx, file in enumerate(os.listdir(self.dir_path)):
            if file.endswith(".tcx"):
                exercise = self.tcx_reader.read(os.path.join(self.dir_path, file), null_value_handling=1)
                exercise_val.append((exercise.start_time, exercise))
            if idx >= READ_LIMIT:
                self.exercises_val = exercise_val
                return self.exercises_val                
        self.exercises_val = exercise_val
        return self.exercises_val
    
    def get_calory_average(self) -> int:
        calories = [e.calories for (d, e) in self.exercises_val]
        avg_calories = np.average(calories)
        return avg_calories
    
    def __exercises_to_df(self):
        columns = ["activity_type", "start_time", "end_time", "calories", "avg_speed", "duration", "distance", "altitude_avg"]
        df = pd.DataFrame([{f: getattr(e, f) for f in columns} for (d, e) in self.exercises_val])
        return df

    def get_exercise_dataframe(self):

        df = self.__exercises_to_df()
        df["start_time"] = pd.to_datetime(df["start_time"])
        df["end_time"] = pd.to_datetime(df["end_time"])

        df = df.dropna(subset=["start_time", "end_time"], how="all")
        iso = df["start_time"].dt.isocalendar()        
        df["iso_year_week"] = iso["year"].astype(str) + "" + iso["week"].astype(str).str.zfill(2)
        print(df)
        return df
    
    def __get_timeframes_per_exercise(self, exercise: TCXExercise) -> pd.DataFrame:
        rows = []
        print(exercise)
        if exercise.trackpoints:
            for tp in exercise.trackpoints:
                rows.append({
                    "time": pd.to_datetime(tp.time, utc=True, errors="coerce"),
                    "h_r": tp.hr_value,
                    "dist_m": tp.distance,
                    "alt_m": tp.elevation,
                    "lat": tp.latitude,
                    "lon": tp.longitude
                })

            df = pd.DataFrame(rows).dropna(subset=["time"]).sort_values("time").drop_duplicates("time")
            for c in ["h_r", "dist_m", "alt_m", "lat", "lon"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            df["dt_s"] = df["time"].diff().dt.total_seconds().clip(lower=0)
            df["speed_mps"] = df["dist_m"].diff() / df["dt_s"].replace(0, np.nan)
            return df.reset_index(drop=True)
        return None

    def __summarize_one_exercise(self, df_ex: pd.DataFrame, config: AthleteConfig) -> dict:
        start = df_ex["time"].iloc[0]
        duration_s = float(df_ex["dt_s"].sum())

        if df_ex["dist_m"].notna().any():
            dist_m = float(df_ex["dist_m"].iloc[-1] - df_ex["dist_m"].iloc[0])
            dist_km = dist_m / 1000.0
        else:
            dist_km = np.nan

        zones = self.__time_in_zones(df_ex, config)

        return {
            "date": start.tz_convert(None).date(),
            "start_time": start,
            "duration_s": duration_s,
            "distance_km": dist_km,
            "avg_h_r": float(df_ex["h_r"].mean(skipna=True)),
            "avg_speed_mps": float(df_ex["speed_mps"].mean(skipna=True)),
            "trimp_bannister": self.__bannister_trimp(df_ex, config),
            "trimp_edwards": self.__edwards_trimp(df_ex, config),
            **zones,
        }


    def __get_exercise_summaries(self) -> pd.DataFrame:
        summaries = []
        config = AthleteConfig()
        for (_, exercise) in self.exercises_val:
            if exercise.activity_type == "Biking":
                df_exer = self.__get_timeframes_per_exercise(exercise)
                if df_exer is not None:
                    dict_exer = self.__summarize_one_exercise(df_exer, config)
                    if dict_exer:
                        summaries.append(dict_exer)
        return pd.DataFrame(summaries).sort_values("start_time")

    def __hrr_intensity(self, h_r: pd.Series, config: AthleteConfig) -> pd.Series:
        return (h_r - config.h_r_rest) / (config.h_r_max - config.h_r_rest)

    def __assign_zones_hrr(self, h_r: pd.Series, config: AthleteConfig) -> pd.Series:
        x = self.__hrr_intensity(h_r, config).clip(lower=0, upper=1.2)
        bounds = np.array(config.h_r_r_bound)
        z = np.digitize(x, bounds, right=True).clip(1, 5)
        return pd.Series(z, index=h_r.index)

    def __time_in_zones(self, df: pd.DataFrame, config: AthleteConfig) -> dict:
        z = self.__assign_zones_hrr(df["h_r"], config)
        return {f"z{k}_sec": float(df.loc[z == k, "dt_s"].sum()) for k in range(1, 6)}
    
    def __bannister_trimp(self, df: pd.DataFrame, cfg: AthleteConfig) -> float:
        dt_min = (df["dt_s"] / 60.0).fillna(0)
        hrr = self.__hrr_intensity(df["h_r"].astype(float), cfg).clip(lower=0, upper=1.2)
        return float((dt_min * hrr * np.exp(cfg.b * hrr)).sum())

    def __edwards_trimp(self, df: pd.DataFrame, cfg: AthleteConfig) -> float:
        z = self.__assign_zones_hrr(df["h_r"], cfg)
        total = 0.0
        for k, coeff in enumerate(cfg.coefficient, start=1):
            minutes = df.loc[z == k, "dt_s"].sum() / 60.0
            total += coeff * minutes
        return float(total)
    
    def __ewma_series(self, daily: pd.Series, tau_days: int) -> pd.Series:
        alpha = 2 / (tau_days + 1)
        return daily.ewm(alpha=alpha, adjust=False).mean()
    
    def build_dashboard(self):
       
        total_summary = self.__get_exercise_summaries()
        
        if total_summary.empty:
            raise ValueError("No usable trackpoints found in given TCX files.")

        total_summary.dropna()

        total_summary["week"] = pd.to_datetime(total_summary["date"]).dt.to_period("W").astype(str)
        total_summary["date"] = pd.to_datetime(total_summary["date"])
        total_summary["speed_kmh"] = total_summary["avg_speed_mps"] * 3.6
        total_summary["duration_min"] = total_summary["duration_s"] / 60
        total_summary["month"] = total_summary["date"].dt.to_period("M").astype(str)
        total_summary["week"] = total_summary["date"].dt.to_period("W").astype(str)

        #weekly_km = total_summary.groupby("week")["distance_km"].sum()        

        daily_load = total_summary.groupby("date")["trimp_bannister"].sum()
        daily_load.index = pd.to_datetime(daily_load.index)
        daily_load = daily_load.asfreq("D", fill_value=0)

        ctl = self.__ewma_series(daily_load, 42)
        atl = self.__ewma_series(daily_load, 7)
        # tsb = ctl - atl

        # --- plots ---
        # fig, axes = plt.subplots()
        # weekly_km.plot()
        # axes.set_title("Weekly mileage (km)")
        # axes.set_xlabel("Week")
        # axes.set_ylabel("km")
        # fig.tight_layout()
        # # plt.show()


        # fig, axes = plt.subplots()
        # atl.plot()
        # axes.set_title("Training load (ATL)")
        # axes.set_xlabel("Date")
        # axes.set_ylabel("TRIMP")
        # fig.tight_layout()
        # # plt.show()

        # fig, axes = plt.subplots()
        # ctl.plot()
        # axes.set_title("Training load (CTL)")
        # axes.set_xlabel("Date")
        # axes.set_ylabel("TRIMP")
        # fig.tight_layout()
        # # plt.show()

        # fig, axes = plt.subplots()
        # weekly_z_hours.plot(kind="bar", stacked=True, ax=axes)
        # axes.set_title("Weekly HR zone distribution (hours)")
        # axes.set_xlabel("Week")
        # axes.set_ylabel("hours")
        # fig.tight_layout()
        # plt.show()

        # print(weekly_z_hours.columns)
        # print(weekly_z_hours.head())
        return total_summary
    
    # zone_cols = [f"z{k}_sec" for k in range(1, 6)]
    # weekly_z_hours = total_summary.groupby("week")[zone_cols].sum().div(3600.0).reset_index()
    # weekly_z_hours["week"] = total_summary["week"]
        
    
    def return_figures(self, total_summary: pd.DataFrame, period):
        # figuero1 = plotlyy.bar(
        #     weekly_z_hours,
        #     x="week",
        #     y=["z1_sec", "z2_sec", "z3_sec", "z4_sec", "z5_sec"],
        #     title="Weekly HR zone distribution (hours)")
        # figuero.show()

        weekly_z_hours = self.hr_zones_summary(total_summary, period)
        figuero1 = plotlyy.pie(
            weekly_z_hours,
            names="category",
            values="value"
        )

        fig2_df = total_summary.copy()
        fig2_df = fig2_df.dropna(subset=["avg_h_r"])
        fig2_df = fig2_df[fig2_df["speed_kmh"] > 0]
        fig2_df["speed_kmh_per_avg_h_r"] = fig2_df["speed_kmh"].fillna(0).div(fig2_df["avg_h_r"])

        figuero2 = plotlyy.scatter(
            fig2_df,
            x="date",
            y="speed_kmh_per_avg_h_r",
            #color="avg_h_r",
            trendline="ols",
            title="Speed/Heart-rate relation vs time"
        )
        # figuero.show()

        figuero3 = plotlyy.scatter(
            total_summary,
            x="avg_h_r",
            y="speed_kmh",
            color="month",
            trendline="ols",
            title="HR vs Speed efficiency"
        )
        # figuero.show()
        speed_bins = np.arange(0, total_summary["speed_kmh"].max() + 3, 3)
        dur_bins = np.arange(0, total_summary["duration_min"].max() + 15, 15)
        total_summary["speed_bin"] = pd.cut(total_summary["speed_kmh"], bins=speed_bins)
        total_summary["dur_bin"]   = pd.cut(total_summary["duration_min"], bins=dur_bins)

        hm = (total_summary.groupby(["dur_bin", "speed_bin"], observed=True)["avg_h_r"]
                .mean()
                .reset_index())

        hm["speed_mid"] = hm["speed_bin"].apply(lambda x: x.mid)
        hm["dur_mid"]   = hm["dur_bin"].apply(lambda x: x.mid)

        figuero4 = plotlyy.density_heatmap(
            hm,
            x="speed_mid",
            y="dur_mid",
            z="avg_h_r",
            histfunc="avg",
            nbinsx=len(speed_bins)-1,
            nbinsy=len(dur_bins)-1,
            labels={"speed_mid":"Avg speed (km/h)", "dur_mid":"Duration (min)", "avg_h_r":"Avg HR (bpm)"},
            title="Heatmap: mean HR by speed × duration"
        )
        # fig.show()

        return figuero1, figuero2, figuero3, figuero4 #total_summary, weekly_km, weekly_z_hours, daily_load, atl

    def hr_zones_summary(self, total_summary: pd.DataFrame, period: str) -> pd.DataFrame:
        df = total_summary.copy()
        df["date"] = pd.to_datetime(df["date"])
        max_date = df["date"].max()

        start = max_date - pd.to_timedelta(period)

        zone_cols = [f"z{i}_sec" for i in range(1, 6)]
        sums = df.loc[df["date"] >= start, zone_cols].sum()

        out = (sums
            .rename_axis("category")
            .reset_index(name="value"))

        return out
