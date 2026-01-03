"""
Streamlit UI for LAIOpt.

This frontend provides:
- Editable, human-friendly block tables
- Explicit compilation into a canonical physical model
- Strict backend execution (baseline + simulated annealing)
- Side-by-side visualization and metrics

The backend is never modified by UI assumptions.
"""

import io
import pandas as pd
import streamlit as st

from laiopt.backend.adapters.csv_loader import load_blocks_csv, load_nets_csv, load_die_from_params
from laiopt.backend.core.baseline import baseline_place
from laiopt.backend.core.sa_engine import simulated_annealing
from laiopt.backend.core.cost import total_cost
from laiopt.frontend.visualization import plot_placement


# -------------------------------
# UI → Canonical Compiler Logic
# -------------------------------

ROLE_BASE_SIZES = {
    "CPU": (10, 10),
    "Accelerator": (10, 10),
    "Cache": (8, 8),
    "Memory": (8, 8),
    "IO": (6, 6),
    "Network": (6, 6),
    "DSP": (7, 7),
    "Display": (7, 7),
}

def compile_blocks_to_canonical(block_df: pd.DataFrame) -> io.StringIO:
    """
    Convert UI block table into canonical CSV (id,width,height,power,heat).
    """
    rows = []

    for _, row in block_df.iterrows():
        block_id = str(row["block_id"]).strip()
        role = str(row["role"]).strip()
        connectivity = int(row["connectivity"])
        power = int(row["power"])
        heat = int(row["heat"])

        base_w, base_h = ROLE_BASE_SIZES.get(role, (6, 6))
        scale = 1.0 + 0.15 * (connectivity - 1)

        width = round(base_w * scale, 2)
        height = round(base_h * scale, 2)

        rows.append({
            "id": block_id,
            "width": width,
            "height": height,
            "power": power,
            "heat": heat,
        })

    canonical_df = pd.DataFrame(rows)
    buffer = io.StringIO()
    canonical_df.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer


# -------------------------------
# Streamlit UI
# -------------------------------

st.set_page_config(page_title="LAIOpt", layout="wide")
st.title("LAIOpt — AI-Assisted Chip Layout Optimization")
st.caption("Explainable, early-stage macro floorplanning demo")

st.sidebar.header("Design Parameters")

die_width = st.sidebar.number_input("Die Width", min_value=10.0, value=100.0)
die_height = st.sidebar.number_input("Die Height", min_value=10.0, value=100.0)

nets_file = st.sidebar.file_uploader("Upload Nets CSV", type="csv")
run_button = st.sidebar.button("Run Optimization")


# -------------------------------
# Sample Editable Block Table
# -------------------------------

st.subheader("Block Attributes (Editable)")

sample_blocks = pd.DataFrame([
    {"block_id": "B1", "role": "CPU",          "connectivity": 3, "power": 3, "heat": 3},
    {"block_id": "B2", "role": "Cache",        "connectivity": 3, "power": 2, "heat": 2},
    {"block_id": "B3", "role": "Memory",       "connectivity": 3, "power": 3, "heat": 2},
    {"block_id": "B4", "role": "Accelerator",  "connectivity": 3, "power": 3, "heat": 3},
    {"block_id": "B5", "role": "IO",            "connectivity": 1, "power": 1, "heat": 1},
    {"block_id": "B6", "role": "Display",      "connectivity": 1, "power": 2, "heat": 1},
    {"block_id": "B7", "role": "DSP",           "connectivity": 2, "power": 2, "heat": 2},
    {"block_id": "B8", "role": "Power",         "connectivity": 1, "power": 3, "heat": 2},
    {"block_id": "B9", "role": "Security",      "connectivity": 1, "power": 1, "heat": 1},
    {"block_id": "B10","role": "Network",       "connectivity": 2, "power": 2, "heat": 1},
])

block_df = st.data_editor(
    sample_blocks,
    num_rows="dynamic",
    use_container_width=True,
)


# -------------------------------
# Run Flow
# -------------------------------

if run_button:
    if nets_file is None:
        st.error("Please upload the Nets CSV file.")
        st.stop()

    # Compile UI table → canonical CSV
    canonical_blocks_csv = compile_blocks_to_canonical(block_df)

    # Load backend models
    blocks = load_blocks_csv(canonical_blocks_csv)
    nets = load_nets_csv(nets_file)
    die = load_die_from_params(die_width, die_height)

    # Baseline
    baseline = baseline_place(blocks, die)
    baseline_cost = total_cost(baseline, blocks, nets, die)

    # Optimization
    optimized, optimized_cost = simulated_annealing(
        blocks,
        nets,
        die,
        random_seed=42
    )

    # Visualization
    st.subheader("Before vs After")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Baseline Layout")
        st.pyplot(plot_placement(baseline, blocks, die, "Baseline"))

    with col2:
        st.markdown("### Optimized Layout (AI-Assisted)")
        st.pyplot(plot_placement(optimized, blocks, die, "Optimized"))

    # Metrics
    st.subheader("Quantitative Impact")
    st.metric("Baseline Cost", f"{baseline_cost:.2f}")
    st.metric("Optimized Cost", f"{optimized_cost:.2f}")
    st.metric("Improvement", f"{baseline_cost - optimized_cost:.2f}")
