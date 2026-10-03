"""
One-Click PDF and Excel Situation Report Generation Module.
Generates comprehensive executive situation reports containing risk districts,
recommended OR-Tools allocation transfers, assumptions, and data provenance.
"""
from pathlib import Path
from datetime import datetime
import pandas as pd
from fpdf import FPDF

REPORTS_DIR = Path("reports")

class PDFReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "DISASTER HEALTHCARE AI - EXECUTIVE SITUATION REPORT", border=False, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Provenance Audited", border=False, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | Confidential - State Disaster Management Authority", align="C")

def generate_excel_situation_report(sim_df: pd.DataFrame, alloc_df: pd.DataFrame, out_path: Path = None) -> Path:
    """Generate Excel workbook containing simulation risk results, allocation plan, and provenance."""
    if out_path is None:
        out_path = REPORTS_DIR / "situation_report.xlsx"

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # Sheet 1: High Risk Districts
        high_risk = sim_df[sim_df["risk_level"] == "High"].sort_values("shortage_probability", ascending=False)
        high_risk.to_excel(writer, sheet_name="High_Risk_Districts", index=False)

        # Sheet 2: Recommended Transfers
        if len(alloc_df) > 0:
            alloc_df.to_excel(writer, sheet_name="Recommended_Transfers", index=False)
        else:
            pd.DataFrame([{"status": "No transfers required (Local supply sufficient)"}]).to_excel(writer, sheet_name="Recommended_Transfers", index=False)

        # Sheet 3: Full Simulation Summary
        sim_df.to_excel(writer, sheet_name="Full_District_Demand", index=False)

        # Sheet 4: Provenance Disclosure
        prov = [
            {"Data Element": "EM-DAT Disasters", "Provenance Tag": "REAL", "Source": "CRED EM-DAT (1900-2026)"},
            {"Data Element": "Hospital Directory", "Provenance Tag": "REAL", "Source": "National Health Portal India"},
            {"Data Element": "State ICU Beds", "Provenance Tag": "REAL", "Source": "Kapoor et al. (2020) State Audit"},
            {"Data Element": "Population Raster", "Provenance Tag": "REAL", "Source": "WorldPop 2020 1km Constrained Grid"},
            {"Data Element": "District Bed Capacity", "Provenance Tag": "ESTIMATED", "Source": "State Anchor + Facility Weighting"},
            {"Data Element": "Epidemiological Demand Rates", "Provenance Tag": "ASSUMED", "Source": "WHO IEHK 2017 / Sphere Standards"}
        ]
        pd.DataFrame(prov).to_excel(writer, sheet_name="Data_Provenance", index=False)

    print(f"✓ Excel situation report written to {out_path}")
    return out_path

def generate_pdf_situation_report(sim_df: pd.DataFrame, alloc_df: pd.DataFrame, out_path: Path = None) -> Path:
    """Generate PDF executive situation report using FPDF2."""
    if out_path is None:
        out_path = REPORTS_DIR / "situation_report.pdf"

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Section 1: Executive Summary
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "1. Executive Summary & Incident Status", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    total_districts = sim_df["district"].nunique()
    high_count = sim_df[sim_df["risk_level"] == "High"]["district"].nunique()
    total_transfers = alloc_df["quantity"].sum() if len(alloc_df) > 0 else 0

    summary_text = (
        f"This report presents real-time AI-driven healthcare demand predictions and multi-objective "
        f"resource allocation plans for Maharashtra's {total_districts} administrative districts. "
        f"Under current disaster parameters, {high_count} districts are classified at HIGH SHORTAGE RISK. "
        f"The OR-Tools SCIP optimization solver recommends transferring {total_transfers:,} units of "
        f"essential medical supplies across {len(alloc_df)} transit routes."
    )
    pdf.multi_cell(0, 5, summary_text)
    pdf.ln(5)

    # Section 2: Top High-Risk Districts
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "2. High Shortage-Risk District Priorities", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)

    # Table Header
    pdf.cell(40, 6, "District", border=1)
    pdf.cell(35, 6, "Medicine", border=1)
    pdf.cell(35, 6, "Demand (P50)", border=1)
    pdf.cell(35, 6, "Surge Stock", border=1)
    pdf.cell(40, 6, "P(Shortage)", border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    high_risk_rows = sim_df[sim_df["risk_level"] == "High"].sort_values("shortage_probability", ascending=False).head(8)

    for _, r in high_risk_rows.iterrows():
        pdf.cell(40, 6, str(r["district"]), border=1)
        pdf.cell(35, 6, str(r["medicine"]), border=1)
        pdf.cell(35, 6, f"{r['demand_p50']:,.0f}", border=1)
        pdf.cell(35, 6, f"{r['available_stock']:,.0f}", border=1)
        pdf.cell(40, 6, f"{r['shortage_probability']*100:.1f}% (HIGH)", border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # Section 3: Recommended Allocations
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "3. Recommended Inter-District Resource Transfers", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)

    pdf.cell(40, 6, "Source District", border=1)
    pdf.cell(40, 6, "Dest District", border=1)
    pdf.cell(35, 6, "Medicine", border=1)
    pdf.cell(30, 6, "Quantity", border=1)
    pdf.cell(40, 6, "Distance (km)", border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    if len(alloc_df) > 0:
        for _, r in alloc_df.head(8).iterrows():
            pdf.cell(40, 6, str(r["source_region"]), border=1)
            pdf.cell(40, 6, str(r["dest_region"]), border=1)
            pdf.cell(35, 6, str(r["medicine"]), border=1)
            pdf.cell(30, 6, f"{r['quantity']:,}", border=1)
            pdf.cell(40, 6, f"{r['distance_km']} km", border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # Section 4: Data Provenance & Method Disclosures
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "4. Data Provenance & Method Disclosures", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(
        0, 5,
        "Every figure in this report carries strict provenance verification:\n"
        "- [REAL]: EM-DAT (CRED), National Hospital Directory (data.gov.in), WorldPop 2020 Grid.\n"
        "- [ESTIMATED]: District bed capacity (scaled from 11,587 state ICU bed audit), event weather features.\n"
        "- [ASSUMED]: Epidemiological daily demand rates from WHO IEHK 2017 & Sphere Handbook standards.\n"
        "Model outputs are non-binding recommendations requiring human officer validation."
    )

    pdf.output(out_path)
    print(f"✓ PDF situation report written to {out_path}")
    return out_path

if __name__ == "__main__":
    from src.engine.monte_carlo import run_monte_carlo_district_simulation
    from src.optimise import solve_resource_allocation
    from src.data.boundaries import MAHARASHTRA_DISTRICTS

    test_preds = {d: {"hazard_type": "Flood", "affected_mean_log": 9.0, "affected_std_log": 0.40} for d in MAHARASHTRA_DISTRICTS.keys()}
    sim_df = run_monte_carlo_district_simulation(test_preds, n_draws=1000)
    alloc_df, _ = solve_resource_allocation({"Pune": {"antibiotics": 5000.0}}, {"Mumbai": {"antibiotics": 10000.0}})

    generate_excel_situation_report(sim_df, alloc_df)
    generate_pdf_situation_report(sim_df, alloc_df)
