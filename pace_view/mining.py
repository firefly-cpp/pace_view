"""
Pattern mining for high-level behavioral rules from historical rides.
"""

import os
import pandas as pd
from niaarm import Dataset, get_rules
from niapy.algorithms.basic import DifferentialEvolution


class PatternMiner:
    """
    Mines human-readable rules that explain performance patterns.
    """
    def __init__(self, population_size=50, max_iters=50, seed=None):
        self.population_size = population_size
        self.max_iters = max_iters
        self.seed = seed

    def _discretize(self, df):
        """
        Transforms continuous physics numbers into qualitative labels.
        """
        data = pd.DataFrame()

        # 1. Discretize wind
        data["Wind"] = pd.cut(
            df["headwind_mps"], bins=[-50, -1, 1, 50], labels=["Tailwind", "Neutral", "Headwind"]
        )

        # 2. Discretize terrain
        data["Terrain"] = pd.cut(df["grad"], bins=[-1, 0.02, 1], labels=["Flat", "Climb"])

        # 3. Discretize status
        if "drift" in df.columns:
            data["Status"] = pd.cut(
                df["drift"], bins=[-100, -5, 5, 100], labels=["High_Performance", "Normal", "Struggling"]
            )
        else:
            data["Status"] = "Normal"

        data = data.dropna()
        return data.loc[:, data.nunique() > 1]

    def _summarize_rules(self, rules):
        """
        Turn raw rule strings into a dashboard-friendly report.
        """
        explanation = (
            "Patterns are mined from discretized wind, terrain, and drift signals and filtered to explain struggling episodes."
        )

        if not rules:
            return {
                "Analysis": "Pattern Mining Report",
                "Summary": "No strong patterns found yet. Need more data.",
                "Top_Rules": [],
                "Insights": ["Collect more rides to strengthen signal for pattern mining."],
                "Explanation": explanation,
            }

        insights = []
        for rule in rules[:5]:
            insights.append(f"Rule indicates struggling when {rule}")

        return {
            "Analysis": "Pattern Mining Report",
            "Summary": f"Discovered {len(rules)} candidate rules.",
            "Top_Rules": rules[:10],
            "Insights": insights,
            "Explanation": explanation,
        }

    def discover_rules(self, full_history_df):
        """
        Uses Nature-Inspired Algorithms to find patterns in the athlete's data / .tcx files.
        Returns a report with insights for the dashboard.
        """
        print("Mining for pattern rules using Differential Evolution...")

        # 1. Prepare data
        discrete_df = self._discretize(full_history_df)

        if discrete_df.empty:
            print("No valid data for mining.")
            return self._summarize_rules([])

        # 2. Create dataset file for NiaARM
        temp_file = "temp_mining_data.csv"
        discrete_df.to_csv(temp_file, index=False)

        try:
            # Load dataset using NiaARM's loader
            dataset = Dataset(temp_file)

            # 3. Configure algorithm (Differential Evolution)
            algo = DifferentialEvolution(
                population_size=self.population_size,
                differential_weight=0.5,
                crossover_probability=0.9,
                seed=self.seed,
            )

            # 4. Run mining
            rules, run_time = get_rules(
                dataset,
                algo,
                metrics=("support", "confidence"),
                max_iters=self.max_iters,
                logging=False,
            )

            # 5. Filter for "Struggling" rules
            interesting_patterns = []
            for rule in rules:
                # Check if this rule explains why we are struggling
                if "Struggling" in str(rule.consequent):
                    interesting_patterns.append(str(rule))

            return self._summarize_rules(interesting_patterns)

        except Exception as e:
            print(f"Mining failed: {e}")
            return self._summarize_rules([])

        finally:
            if os.path.exists(temp_file):  # Cleanup temp file
                os.remove(temp_file)