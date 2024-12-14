# Qcells Optimization Engineer Take Home Problem

This repository contains code to optimize the dispatch of a Behind-the-Meter (BTM) battery energy storage system to minimize total electricity costs over a 24-hour period. The code demonstrates object-oriented programming principles, mathematical optimization modeling, and the use of CVXPY as the optimization interface.

---

## Repository Structure

- **main.py**: Entry point of the code that:
  1. Loads `profiles.csv`
  2. Sets price parameters
  3. Calls the `run_optimization` method
  4. Writes `results.csv` containing the optimized dispatch schedule.

- **optimizer.py**: Defines the `Optimizer` class that:
  1. Builds the optimization model with variables, constraints, and objective.
  2. Solves the optimization problem.
  3. Returns the solution for battery dispatch and meter values.

- **profiles.csv**: Contains the input load and PV time series data.

- **requirements.txt**: List of required Python packages to run the code. Installing these in a fresh environment is recommended.

- **results.csv**: Generated after running `main.py`, includes `Time`, `AC Battery Power (kW)`, and `Meter (kW)` with the optimal solution.

- **report.pdf**: A write-up detailing the modeling approach, assumptions, and results (optional).

---

## Prerequisites

- Python 3.9 or later (recommended)
- A virtual environment tool (e.g., `venv`, `conda`) is recommended.
- CVXPY and XPRESS solver installed. The XPRESS solver can be acquired through the free community license included in the `requirements.txt` package list.

---

## Installation Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/foad77/Qcells_Take-Home.git
cd Qcells_Take-Home
```
----
### 2. Create and Activate a Virtual Environment (Optional)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```
### 4. Running the Code

```bash
python main.py
```


