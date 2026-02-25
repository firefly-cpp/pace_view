# 🚴‍♂️ Physics-Augmented Contextual Explainer and Visual Interface for Endurance Workflows

**AST-Monitor-AI** is a companion repository to [AST-Monitor](https://github.com/firefly-cpp/AST-Monitor), focused on integrating **machine learning**, **data mining**, and **AI-powered insights** into cycling (and potentially running) performance analysis.

## 🧠 Key Goals

- Analyze session data for **performance patterns** and **fatigue signatures**
- Build **predictive models** for pacing, recovery, and training load
- Support intelligent **adaptive training plans**
- Enable **visual analytics dashboards** or coach-level summaries
- Provide modular tools that work with AST-Monitor logs or live data

## 🔑 License

This package is distributed under the MIT License. This license can be found online
at <http://www.opensource.org/licenses/MIT>.

## Disclaimer

This framework is provided as-is, and there are no guarantees that it fits your purposes or that it is bug-free. Use it
at your own risk!

## 📖 Further read
[1] [Awesome Computational Intelligence in Sports](https://github.com/firefly-cpp/awesome-computational-intelligence-in-sports)

## 🔗 Related packages/frameworks

[1] [sport-activities-features: A minimalistic toolbox for extracting features from sports activity files written in Python](https://github.com/firefly-cpp/sport-activities-features)

[2] [ast-tdl: Training Description Language for Artificial Sport Trainer](https://github.com/firefly-cpp/ast-tdl)

## 📝 References

Fister Jr, I., Fister, I., Iglesias, A., Galvez, A., Deb, S., & Fister, D. (2021). On deploying the Artificial Sport
Trainer into practice. arXiv preprint [arXiv:2109.13334](https://arxiv.org/abs/2109.13334).

Fister Jr, I., Salcedo-Sanz, S., Iglesias, A., Fister, D., Gálvez, A., & Fister, I. (2021). New Perspectives in the
Development of the Artificial Sport Trainer. Applied Sciences, 11(23), 11452.
DOI: [10.3390/app112311452](https://doi.org/10.3390/app112311452)

## Install guide

```
pip install -e packages/trendboard
pip install -e packages/envimpact
```

## Run the dashboard

Install the requirements specified in `requirements.txt` and then execute
```
python app.py
```

## Run context trainer text-only example

```
python examples/context_trainer_text_example.py
```

## Overview

This repository provides a full workflow for cycling activity analysis:
- Parse raw TCX files into structured activity data
- Clean and align signals with optional weather context
- Compute physics-based features like headwind, gradient, and virtual power
- Train a digital twin to predict expected physiology
- Generate counterfactual explanations and human-readable rationales
- Mine global patterns across historical rides

The pipeline is modular, so you can use just parsing/cleaning or the full end-to-end flow.

## Architecture

Add architecture image here:

```
[ PLACEHOLDER: architecture diagram image ]
```

## Repository Structure

- `pace_view/` core pipeline modules
- `data/` sample TCX files for local testing
- `tests/` pytest unit tests
- `scripts/` local helpers and experiments
- `assets/` images and supporting artifacts

## Core Components

- `pace_view/data_parsing.py` loads TCX files and optional weather context
- `pace_view/data_cleaning.py` builds aligned dataframes
- `pace_view/physics.py` computes headwind, gradient, and virtual power
- `pace_view/digital_twin.py` predicts expected HR and drift
- `pace_view/counterfactual.py` and `pace_view/rationale.py` build explanations
- `pace_view/mining.py` mines interpretable rules using NiaARM

## Data Flow (high level)

1. Parse TCX -> activity arrays + weather
2. Clean + align -> dataframe
3. Physics features -> headwind, gradient, virtual power
4. Digital twin -> predicted HR and drift
5. Counterfactual + rationale -> explanation output
6. Pattern mining -> global rules across rides

## Testing

Run from repo root:

```
python -m pytest -q
```

If you use a specific interpreter:

```
<path/to/your/python/>python.exe -m pytest -q
```

## Configuration (Weather API)

If you want weather enrichment, provide an API key via environment variables:

```
WEATHER_API_KEY=<your_key_here>
```

Examples using `ContextTrainer` now resolve the key centrally via `pace_view.config.get_weather_api_key()`.
It checks the process environment first and also loads a project-root `.env` file if present.

Optional manual loading with `python-dotenv`:

```
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.getenv("WEATHER_API_KEY")
```

## Examples

The examples below show how to run the core pipeline in code:
- The programmatic example trains the model on a folder of TCX files and then mines global rules.
- The single-file example runs the full explainability flow for one ride and returns a rationale report.

Use these as starting points and adjust `history_folder` or the input file path to match your local data.
