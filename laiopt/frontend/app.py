"""
Streamlit UI for LAIOpt.

Provides an end-to-end interface for:
- Loading CSV inputs
- Running baseline placement
- Running simulated annealing optimization
- Visualizing and comparing results
"""

import streamlit as st

from laiopt.backend.adapters.csv_loader import (
    load_blocks_csv,
    load_nets_csv,
    load_die_from_params,
)
from laiopt.backend.core.baseline import baseline_place
from laiopt.backend.core.sa_engine import simulated_annealing
from laiopt.backend.core.cost import total_cost
from laiopt.frontend.visualization import plot_placement


st.set_page_config(page_title="LAIOpt", layout="wide")
st.title("LAIOpt — AI-Assisted Chip Layout Optimization (Explainable Demo)")

st.sidebar.header("Input Parameters")

blocks_file = st.sidebar.file_uploader("Upload Blocks CSV", type="csv")
nets_file = st.sidebar.file_uploader("Upload Nets CSV", type="csv")

die_width = st.sidebar.number_input("Die Width", min_value=1.0, value=100.0)
die_height = st.sidebar.number_input("Die Height", min_value=1.0, value=100.0)

run_button = st.sidebar.button("Run Optimization")

if run_button:
    if blocks_file is None or nets_file is None:
        st.error("Please upload both Blocks and Nets CSV files.")
        st.stop()

    # Load inputs
    blocks = load_blocks_csv(blocks_file)
    nets = load_nets_csv(nets_file)
    die = load_die_from_params(die_width, die_height)

    # Baseline placement
    baseline = baseline_place(blocks, die)
    baseline_cost = total_cost(baseline, blocks, nets, die)

    # Optimized placement
    optimized, optimized_cost = simulated_annealing(
        blocks,
        nets,
        die,
        random_seed=42
    )

    # Display results
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Baseline Placement")
        fig = plot_placement(baseline, blocks, die, "Baseline Placement")
        st.pyplot(fig)
        st.metric("Baseline Cost", f"{baseline_cost:.2f}")

    with col2:
        st.subheader("Optimized Placement")
        fig = plot_placement(optimized, blocks, die, "Optimized Placement")
        st.pyplot(fig)
        st.metric("Optimized Cost", f"{optimized_cost:.2f}")

    st.subheader("Cost Comparison")
    st.write({
        "Baseline Cost": baseline_cost,
        "Optimized Cost": optimized_cost,
        "Improvement": baseline_cost - optimized_cost
    })
