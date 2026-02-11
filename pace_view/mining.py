import pandas as pd
import os
from niaarm import Dataset, get_rules
from niapy.algorithms.basic import DifferentialEvolution

class PatternMiner:
    def __init__(self):
        pass

    def _discretize(self, df):
        """
        Transforms continuous physics numbers into qualitative labels
        """
        data = pd.DataFrame()
        
        # 1. Discretize wind
        data['Wind'] = pd.cut(df['headwind_mps'], 
                              bins=[-50, -1, 1, 50], 
                              labels=['Tailwind', 'Neutral', 'Headwind'])

        # 2. Discretize terrain
        data['Terrain'] = pd.cut(df['grad'], 
                                 bins=[-1, 0.02, 1], 
                                 labels=['Flat', 'Climb'])

        # 3. Discretize status
        if 'drift' in df.columns:
            data['Status'] = pd.cut(df['drift'], 
                                    bins=[-100, -5, 5, 100], 
                                    labels=['High_Performance', 'Normal', 'Struggling'])
        else:
            data['Status'] = 'Normal'
        
        return data.dropna()

    def discover_rules(self, full_history_df):
        """
        Uses Nature-Inspired Algorithms to find patterns in the athlete's data / .tcx files
        """
        print("Mining for pattern rules using Differential Evolution...")
        
        # 1. Prepare data
        discrete_df = self._discretize(full_history_df)
        
        if discrete_df.empty:
            print("No valid data for mining.")
            return []

        # 2. Create dataset file for NiaARM
        temp_file = 'temp_mining_data.csv'
        discrete_df.to_csv(temp_file, index=False)
        
        try:
            # Load dataset using NiaARM's loader
            dataset = Dataset(temp_file)
            
            # 3. Configure algorithm (Differential Evolution)
            algo = DifferentialEvolution(
                population_size=50, 
                differential_weight=0.5, 
                crossover_probability=0.9
            )
            
            # 4. Run mining
            rules, run_time = get_rules(
                dataset, 
                algo, 
                metrics=('support', 'confidence'), 
                max_iters=50, 
                logging=False
            )
            
            # 5. Filter for "Struggling" rules
            interesting_patterns = []
            for rule in rules:
                rule_str = str(rule)
                
                # Check if this rule explains why we are struggling
                if "Struggling" in rule_str and "THEN" in rule_str:
                    if rule_str.split("THEN")[1].find("Struggling") != -1: # Verify consequent
                        interesting_patterns.append(rule_str)

            return interesting_patterns

        except Exception as e:
            print(f"Mining failed: {e}")
            return []
            
        finally:
            if os.path.exists(temp_file): # Cleanup temp file
                os.remove(temp_file)
