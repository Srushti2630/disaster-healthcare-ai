#!/usr/bin/env python3
"""
Master entry-point script to run the end-to-end Disaster Healthcare AI pipeline.
Usage:
  python run_all.py [stage]
Stages:
  data     - Build real data layer (boundaries, population, facilities, disasters, weather)
  train    - Train impact model, CQR conformal intervals, and SHAP explainers on real data
  engine   - Run transparent demand engine & Monte-Carlo risk simulations
  optimise - Run OR-Tools SCIP stochastic resource allocation MIP solver
  test     - Run complete pytest suite
  app      - Launch interactive Streamlit decision dashboard
  all      - Execute data -> train -> engine -> optimise -> test
"""
import sys
import subprocess
from pathlib import Path

PYTHON_BIN = sys.executable

def run_command(cmd, desc):
    print(f"\n==========================================")
    print(f"Executing: {desc}")
    print(f"Command: {' '.join(cmd)}")
    print(f"==========================================")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"ERROR: Stage '{desc}' failed with exit code {res.returncode}")
        sys.exit(res.returncode)

def run_data():
    run_command([PYTHON_BIN, "-m", "src.data.build_data_layer"], "Build Real Data Layer")

def run_train():
    run_command([PYTHON_BIN, "-m", "src.models.train_impact_model"], "Train Real EM-DAT Impact Model & CQR")

def run_engine():
    run_command([PYTHON_BIN, "-m", "src.engine.run_simulation"], "Run Transparent Epidemiological & Monte-Carlo Engine")

def run_optimise():
    run_command([PYTHON_BIN, "-m", "src.optimise"], "Run Stochastic MIP Optimization Solver")

def run_test():
    run_command([PYTHON_BIN, "-m", "pytest", "-v"], "Run Test Suite")

def run_app():
    run_command([PYTHON_BIN, "-m", "streamlit", "run", "app.py"], "Launch Streamlit Decision Support Dashboard")

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target == "data":
        run_data()
    elif target == "train":
        run_train()
    elif target == "engine":
        run_engine()
    elif target == "optimise":
        run_optimise()
    elif target == "test":
        run_test()
    elif target == "app":
        run_app()
    elif target == "all":
        run_data()
        run_train()
        run_engine()
        run_optimise()
        run_test()
        print("\nPipeline execution complete! Run 'python run_all.py app' to launch the decision dashboard.")
    else:
        print(f"Unknown target: {target}")
        print("Available targets: data, train, engine, optimise, test, app, all")
        sys.exit(1)

if __name__ == "__main__":
    main()
