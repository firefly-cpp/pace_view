from pace_view.data_parsing import DataParser
from pace_view.data_cleaning import DataCleaner
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# # if __name__ == "__main__":
#     # init tcx-reader
# dirname = os.path.dirname(__file__)
# directory_name = os.path.join(dirname, 'tcx_path')    
# parser = DataParser()
# cleaner = DataCleaner()
# exercises = parser.parse_tcx_directory(directory_name)

#     # calc average calories through multiple sessions
#     # calories = reader.get_calory_average()
#     # print(calories)

#     # df = reader.get_exercise_dataframe()
#     # df = df[df["activity_type"] == "Biking"]
#     # df = df.sort_values("start_time")
#     # df["avg_speed_per_avg_altitude"] = df["avg_speed"] / df["altitude_avg"]
#     # #group sessions by week
    
#     # data_1 = df[["start_time", "avg_speed_per_avg_altitude"]]

#     # fig, axes = plt.subplots(2, 1, figsize=(12, 9))
#     # # Distance vs avg_speed (colored by start_time)
#     # sc1 = axes[0].plot(        
#     #     data_1["start_time"],
#     #     data_1["avg_speed_per_avg_altitude"]        
#     # )
#     # axes[0].set_xlabel("start time")
#     # axes[0].set_ylabel("avgerage speed to average altitude")
#     # plt.show()
# total_summary = reader.build_dashboard()

from pace_view.core import ContextTrainer

# 1. Setup: Point to the folder of files
# The library automatically handles hundreds of files, physics, and weather.
trainer = ContextTrainer(
    history_folder='./data', 
    weather_api_key='<YOUR_API_KEY>'  # Visual Crossing API Key
)

# 2. Train: Builds the "Digital Twin" from the history
# This runs the ingestion -> physics -> machine learning pipeline internally.
trainer.fit()

# 3. Explain: Pass a new file to get the "Why"
# The library compares this ride against the trained model.
insight = trainer.explain('./data/9.tcx')

print(insight)


# 4. Test reading
dirname = os.path.dirname(__file__)
directory_name = os.path.join(dirname, 'tcx_path')
parser = DataParser()
cleaner = DataCleaner()
exercises = parser.parse_tcx_directory(directory_name)
total_summary = cleaner.build_dashboard(exercises)
# Output: 
# "Performance Gap: -15 Watts. 
#  Primary Cause: Headwind (contributed -12W). 
#  Secondary Cause: Heat Stress (HR +8bpm drift)."
    
    
