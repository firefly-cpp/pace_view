🚴‍♂️ PACE-VIEW: Explainable Cycling Intelligence Dashboard
==========================================================

PACE-VIEW turns raw TCX rides into decision-ready insights for athletes and coaches.  
It combines physics-informed modeling, digital-twin prediction, and explainable AI in one interactive dashboard.

💪 Why PACE-VIEW?
-----------------

- **Dashboard-first workflow**: Inspect workload, HR zone mix, efficiency trends, and per-session explanations in one place.
- **Explainability by design**: Use counterfactual analysis, rationale generation, and pattern mining to understand *why* a session felt hard or easy.
- **Physics + ML pipeline**: Quantify wind/terrain/environmental load and compare expected vs observed physiology.
- **Modular architecture**: Run the full web app or use components independently in scripts.

↗️ Quick Start
--------------

Run the full dashboard:

.. code-block:: bash

   python examples/full_dashboard.py

Then open an activity to view detailed explanations and decision-support outputs.

- **Free software**: MIT license  
- **Python versions**: 3.8.x, 3.9.x, 3.10.x, 3.11.x, 3.12.x  
- **Documentation**: https://pace-view.readthedocs.io/en/latest/  
- **Tested OS**: Windows, Ubuntu, Fedora, Alpine, Arch, macOS  
  (This does not imply it will not work on others.)

📦 Installation
---------------

Install PACE-VIEW with pip:

.. code-block:: bash

   pip install pace_view

To install from source:

.. code-block:: bash

   git clone https://github.com/firefly-cpp/pace_view.git
   cd pace_view
   poetry build
   python setup.py build

✨ Implemented Components
-------------------------

.. image:: https://raw.githubusercontent.com/firefly-cpp/pace_view/refs/heads/main/.github/img/architecture.png
   :alt: PACE-VIEW architecture
   :align: center

Component 1: Data Ingestion & Preprocessing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Loads raw activity and weather signals, aligns timestamps, and builds clean dataframes for downstream modeling.

**Classes/modules:**

- ``DataParser`` (``pace_view/data_parsing.py``)
- ``DataCleaner`` (``pace_view/data_cleaning.py``)

Component 2: Environmental Quantification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Quantifies external/mechanical load and learns expected physiological behavior from historical rides.

**Classes/modules:**

- ``PhysicsEngine`` (``pace_view/physics.py``)
- ``DigitalTwinModel`` (``pace_view/digital_twin.py``)

Component 3: Explainable AI (XAI)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Explains deviations with counterfactual reasoning, generates human-readable rationales, and mines global patterns.

**Classes/modules:**

- ``CounterfactualAnalyzer`` (``pace_view/counterfactual.py``)
- ``RationaleGenerator`` (``pace_view/rationale.py``)
- ``PatternMiner`` (``pace_view/mining.py``)

Component 4: Interactive Dashboard & Decision Support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Exposes session-level explanation and inter-session analysis through the web UI and example views.

**Classes/modules:**

- ``ContextTrainer`` (``pace_view/core.py``)
- Flask/Dash app: ``examples/full_dashboard.py``

📓 Examples
-----------

Run these from the repository root:

1. **Full Dashboard**

   .. code-block:: bash

      python examples/full_dashboard.py

   Runs the full interactive dashboard with all cards and activity detail routing.  
   End-to-end example combining visualization and contextual explanations.

2. **Activity Detail Page**

   .. code-block:: bash

      python examples/activity_detail_page_example.py

   Serves only the activity detail page for a single example TCX activity.

3. **ContextTrainer (CLI Text Example)**

   .. code-block:: bash

      python examples/context_trainer_text_example.py

   Runs ContextTrainer without Flask or Dash and prints text-only results to the terminal.

4. **HR Zone Mix Card**

   .. code-block:: bash

      python examples/hr_zone_mix_example.py

   Demonstrates the zone-distribution visualization in isolation.

5. **Efficiency Over Time Card**

   .. code-block:: bash

      python examples/efficiency_over_time_example.py

   Shows how rolling-window controls affect the efficiency plot.

6. **HR vs Speed x Duration Heatmap**

   .. code-block:: bash

      python examples/hr_vs_speed_duration_example.py

   Demonstrates the binned relationship between duration, speed, and heart rate.

Repository Structure
--------------------

- ``pace_view/`` - Core pipeline modules  
- ``data/`` - Sample TCX files for local testing  
- ``tests/`` - Pytest unit tests  
- ``scripts/`` - Local helpers and experiments  
- ``assets/`` - Images and supporting artifacts  

Core Components Overview
------------------------

- ``pace_view/data_parsing.py`` - Loads TCX files and optional weather context  
- ``pace_view/data_cleaning.py`` - Builds aligned dataframes  
- ``pace_view/physics.py`` - Computes headwind, gradient, and virtual power  
- ``pace_view/digital_twin.py`` - Predicts expected HR and drift  
- ``pace_view/counterfactual.py`` - Counterfactual explanations  
- ``pace_view/rationale.py`` - Human-readable rationales  
- ``pace_view/mining.py`` - Mines interpretable rules using NiaARM  

Data Flow (High Level)
----------------------

1. Parse TCX → activity arrays + weather  
2. Clean + align → dataframe  
3. Physics features → headwind, gradient, virtual power  
4. Digital twin → predicted HR and drift  
5. Counterfactual + rationale → explanation output  
6. Pattern mining → global rules across rides  

Testing
-------

Run from repository root:

.. code-block:: bash

   python -m pytest -q

Using a specific interpreter:

.. code-block:: bash

   <path/to/your/python/>python.exe -m pytest -q

Configuration (Weather API)
---------------------------

To enable weather enrichment, provide an API key via environment variables:

.. code-block:: bash

   WEATHER_API_KEY=<your_key_here>

Examples using ``ContextTrainer`` resolve the key centrally via
``pace_view.config.get_weather_api_key()``.

The method checks:

- Process environment variables  
- A project-root ``.env`` file (if present)

Optional manual loading using ``python-dotenv``:

.. code-block:: python

   from dotenv import load_dotenv
   import os

   load_dotenv()
   api_key = os.getenv("WEATHER_API_KEY")

🔑 License
----------

This package is distributed under the MIT License:

http://www.opensource.org/licenses/MIT

Disclaimer
----------

This framework is provided as-is. There are no guarantees that it fits your purposes or that it is bug-free. Use it at your own risk.

📖 Further Reading
------------------

- Awesome Computational Intelligence in Sports  
  https://github.com/firefly-cpp/awesome-computational-intelligence-in-sports

🔗 Related Packages / Frameworks
--------------------------------

1. **sport-activities-features**  
   https://github.com/firefly-cpp/sport-activities-features  

2. **ast-tdl**  
   https://github.com/firefly-cpp/ast-tdl  

3. **NiaAML**  
   https://github.com/firefly-cpp/niaaml  

📝 References
-------------

Fister Jr, I., Fister, I., Iglesias, A., Galvez, A., Deb, S., & Fister, D. (2021).  
*On deploying the Artificial Sport Trainer into practice.*  
arXiv preprint: https://arxiv.org/abs/2109.13334  

Fister Jr, I., Salcedo-Sanz, S., Iglesias, A., Fister, D., Gálvez, A., & Fister, I. (2021).  
*New Perspectives in the Development of the Artificial Sport Trainer.*  
Applied Sciences, 11(23), 11452.  

DOI: https://doi.org/10.3390/app112311452  
