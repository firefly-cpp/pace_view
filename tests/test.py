import pandas as pd
import pytest

from pace_view.data_parsing import DataParser
from pace_view.data_cleaning import DataCleaner
from pace_view.physics import PhysicsEngine
from pace_view.core import ContextTrainer

import os

# DO NOT CHANGE TEST DATASET - SOME ASSERTS IN TESTS RELY ON THAT

#data parsing test on a single tcx file
def test_data_parsing_with_tcx_file():
    tcx_path = "tests/data/1.tcx"

    parser = DataParser(weather_api_key=None)

    result = parser.parse_file(tcx_path, is_training=True)
    assert result is not None

    activity, weather = result

    assert "Biking" in activity.get("activity_type", "")
    assert len(activity["timestamps"]) > 0
    assert len(weather) == len(activity["timestamps"])    


#data parsing test on a single tcx file with weather api enabled
def test_data_parsing_with_tcx_file_with_weather():
    tcx_path = "tests/data/1.tcx"

    weather_api_key = os.getenv('weather_api_key')

    parser = DataParser(weather_api_key=weather_api_key)

    result = parser.parse_file(tcx_path, is_training=True)
    assert result is not None

    activity, weather = result

    assert "Biking" in activity.get("activity_type", "")
    assert len(activity["timestamps"]) > 0
    assert len(weather) == len(activity["timestamps"])
    assert weather[0]['temp'] >= -20
    assert weather[0]['hum'] >= 0


#data cleaning test on a single tcx file
def test_data_cleaning_after_parsing():
    tcx_path = "tests/data/1.tcx"
    parser = DataParser(weather_api_key=None)
    cleaner = DataCleaner(parser)

    parsed = parser.parse_file(tcx_path, is_training=True)
    assert parsed is not None

    act, weather = parsed
    df = cleaner.to_dataframe(act, weather)

    assert df is not None
    assert len(df) > 0
    assert "speed_mps" in df.columns
    assert pd.api.types.is_numeric_dtype(df["speed_mps"])


#test the mining on fifty files
#this test only runs if niaarm is installed
def test_mining_with_fifty_tcx_files(monkeypatch):
    pytest.importorskip("niaarm")
    pytest.importorskip("niapy")
    weather_api_key = None
    TARGET_FILE = "tests/data/1.tcx"

    trainer = ContextTrainer(
        history_folder="tests/data/",
        weather_api_key=weather_api_key
    )

    trainer.fit()

    cache_path = "tests/data/history_cache.csv"
    df_history = pd.read_csv(cache_path)
    assert "drift" in df_history.columns

    _ = trainer.mine_patterns() or {}
    activity_report = trainer.explain(TARGET_FILE) or {}

    print(activity_report)

    assert isinstance(activity_report, dict)
    assert "Summary_Metrics" in activity_report
    assert "Rationales" in activity_report
    assert "Atmosphere" in activity_report["Rationales"]
    assert "NOT ASSESSED" in activity_report["Rationales"]["Atmosphere"]
