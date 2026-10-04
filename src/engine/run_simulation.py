"""
Master runner for Phase 3 Transparent Demand & Monte-Carlo Simulation Engine.
Runs 2,000+ Monte-Carlo draws across all 35 Maharashtra districts, outputs P10/P50/P90 demand bands,
trains the fast ML surrogate, and archives the legacy synthetic demand generator.
"""
from pathlib import Path
import os
import shutil
import json
import pandas as pd

from src.engine.monte_carlo import run_monte_carlo_district_simulation
from src.engine.demand import get_impact_sigma
from src.models.surrogate import train_surrogate_classifier
from src.data.boundaries import MAHARASHTRA_DISTRICTS

PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
ARCHIVE_DIR = Path("archive/legacy_synthetic")

def archive_legacy_synthetic_generator():
    """Archive legacy synthetic_demand.py script and datasets per Rule 1 & Phase 3 rules."""
    old_script = Path("scripts/synthetic_demand.py")
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    if old_script.exists():
        dest_script = ARCHIVE_DIR / "synthetic_demand.py"
        shutil.move(str(old_script), str(dest_script))
        print(f"✓ Archived legacy synthetic generator to {dest_script}")

    # Write warning README in archive folder
    readme_path = ARCHIVE_DIR / "README.md"
    readme_content = """# Legacy Synthetic Generator Archive

> [!WARNING]
> This folder contains the legacy `synthetic_demand.py` script and old synthetic datasets.
> **They are completely archived and no longer used anywhere in the live pipeline.**
> The live framework now uses real EM-DAT historical disaster data, WorldPop population rasters,
> National Hospital Directory data, and transparent WHO IEHK / Sphere Monte-Carlo simulations.
"""
    readme_path.write_text(readme_content)

def run_simulation_engine():
    print("==================================================")
    print("Running Phase 3 Transparent Demand & Monte-Carlo Engine...")
    print("==================================================")

    model_sigma = get_impact_sigma("model_prediction")

    # Prepare default district disaster impact scenario (Flood event across Maharashtra)
    district_impact_inputs = {}
    for idx, d_name in enumerate(MAHARASHTRA_DISTRICTS.keys()):
        # High impact for major flood-prone districts (Pune, Kolhapur, Sangli, Raigad, Mumbai)
        if d_name in ["Pune", "Kolhapur", "Sangli", "Raigad", "Mumbai", "Solapur", "Satara", "Nashik"]:
            aff_log = 10.5
            inj_log = 7.5
        else:
            aff_log = 8.0
            inj_log = 5.2

        district_impact_inputs[d_name] = {
            "hazard_type": "Flood",
            "affected_mean_log": aff_log,
            "affected_std_log": model_sigma,
            "injured_mean_log": inj_log,
            "injured_std_log": 0.50
        }

    # Run Monte-Carlo simulation with 2,000 draws
    sim_df = run_monte_carlo_district_simulation(
        district_impact_predictions=district_impact_inputs,
        n_draws=2000,
        horizon_days=7,
        random_seed=42
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_sim_csv = PROCESSED_DIR / "simulation_summary.csv"
    sim_df.to_csv(out_sim_csv, index=False)
    print(f"✓ Completed 2,000 Monte-Carlo draws for {len(sim_df)} district x medicine pairs.")
    print(f"✓ Output saved to {out_sim_csv}")

    # Train fast ML surrogate classifier on 500 diverse Monte-Carlo scenarios
    surrogate_bundle = train_surrogate_classifier(n_scenarios=500)

    # Archive legacy generator
    archive_legacy_synthetic_generator()

    print("\nPhase 3 Transparent Demand & Monte-Carlo Engine completed successfully!")

if __name__ == "__main__":
    run_simulation_engine()
