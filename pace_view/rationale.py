"""
Human-readable explanations built from counterfactual signals.
"""

import pandas as pd

class RationaleGenerator:
    """
    Turns counterfactual signals into user-facing rationales.
    """

    def __init__(
        self,
        headwind_threshold_mps=3.0,
        headwind_pct_threshold=25.0,
        tailwind_threshold_mps=-1.0,
        climb_grade_threshold=0.03,
        heat_penalty_bpm=3.0,
    ):
        self.headwind_threshold_mps = headwind_threshold_mps
        self.headwind_pct_threshold = headwind_pct_threshold
        self.tailwind_threshold_mps = tailwind_threshold_mps
        self.climb_grade_threshold = climb_grade_threshold
        self.heat_penalty_bpm = heat_penalty_bpm

    def build_rationales(self, df):
        """
        Create short, natural-language rationale statements.
        """
        rationales = {}

        # 1. Wind rationale (impact distribution)
        minutes_in_headwind = len(df[df["headwind_mps"] > self.headwind_threshold_mps]) / 60
        total_minutes = len(df) / 60
        pct_headwind = (minutes_in_headwind / total_minutes) * 100 if total_minutes > 0 else 0

        if pct_headwind > self.headwind_pct_threshold:
            rationales["Wind"] = (
                f"NEGATIVE: Battled Headwinds for {minutes_in_headwind:.0f} mins ({pct_headwind:.0f}% of ride)."
            )
        elif pct_headwind < 5 and df["headwind_mps"].mean() < self.tailwind_threshold_mps:
            rationales["Wind"] = "ASSISTED: Mostly tailwinds."
        else:
            rationales["Wind"] = "NEUTRAL: Mostly calm winds."

        # 2. Gravity rationale (mechanical)
        minutes_climbing = len(df[df["grad"] > self.climb_grade_threshold]) / 60
        if minutes_climbing > 20:
            rationales["Terrain"] = f"HIGH RESISTANCE: {minutes_climbing:.0f} mins of steep climbing."
        else:
            rationales["Terrain"] = "NEUTRAL: Terrain was mostly flat/rolling."

        # 3. Thermal rationale (temperature/humidity part of the scenario comparison only)
        avg_thermal_penalty = df["env_penalty_thermal_bpm"].mean()
        if pd.isna(avg_thermal_penalty):
            rationales["Atmosphere"] = "NOT ASSESSED: No observed weather data."
        elif avg_thermal_penalty > self.heat_penalty_bpm:
            rationales["Atmosphere"] = (
                f"HEAT STRESS: Model attributes +{avg_thermal_penalty:.1f} bpm to temperature/humidity vs. reference conditions."
            )
        elif avg_thermal_penalty < -self.heat_penalty_bpm:
            rationales["Atmosphere"] = (
                f"COOLING EFFECT: Model attributes {avg_thermal_penalty:.1f} bpm to temperature/humidity vs. reference conditions."
            )
        else:
            rationales["Atmosphere"] = "NEUTRAL: Temperature/humidity effect within 3 bpm of reference conditions."

        return rationales

    def summarize_metrics(self, df):
        """
        Produce compact summary metrics for a report.
        """
        return {
            "Avg_Speed": f"{df['speed_mps'].mean() * 3.6:.1f} km/h",
            "Avg_Power": f"{df['virtual_power'].mean():.0f} W",
            "Avg_HR": f"{df['hr'].mean():.0f} bpm",
            "Avg_Temp": f"{df['temp'].mean():.1f} C",
        }

    def generate_conclusion(self, rationales):
        """
        Turn key rationales into a single concluding sentence.
        """
        factors = []
        for value in rationales.values():
            if "NEGATIVE" in value or "HIGH" in value or "STRESS" in value:
                factors.append(value)
        if not factors:
            return "No adverse conditions flagged by the rule-based checks."
        return " | ".join(factors)

    def build_report(self, df):
        """
        Build a complete explanation report for the dashboard.
        """
        rationales = self.build_rationales(df)
        return {
            "Analysis": "Contextual Intelligence Report",
            "Summary_Metrics": self.summarize_metrics(df),
            "Rationales": rationales,
            "Conclusion": self.generate_conclusion(rationales),
        }
