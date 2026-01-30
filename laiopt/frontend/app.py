"""
LAIOpt Frontend — AI-Assisted Floorplanning

"""

import io
import sys

from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import time
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from collections import defaultdict



from laiopt.backend.adapters.csv_loader import load_blocks_csv, load_nets_csv
from laiopt.backend.core.baseline import baseline_place
from laiopt.backend.core.sa_engine import simulated_annealing
from laiopt.backend.core.cost import (
    total_cost, compute_hpwl_wirelength, compute_overlap_penalty, 
    compute_thermal_penalty, compute_boundary_penalty, compute_center_penalty,
    OVERLAP_WEIGHT, THERMAL_PENALTY_WEIGHT, BOUNDARY_PENALTY, CENTER_PENALTY_WEIGHT
)
from laiopt.frontend.visualization import plot_placement
from laiopt.backend.core.models import Die

# -----------------------------
# Streamlit UI Configuration
# -----------------------------

# --- Custom CSS for Metrics ---
st.markdown("""
<style>
    div[data-testid="stMetricValue"] { font-size: 18px; }
    .stProgress > div > div > div > div { background-color: #4CAF50; }
</style>
""", unsafe_allow_html=True)

st.set_page_config(layout="wide", page_title="LAIOpt")
st.title("LAIOpt —  AI-Assisted Floorplanning Layout Optimizer")

with st.expander("How does the optimization work?", expanded=False):
    st.markdown("""
    **Baseline Placement with ML Agent:** A deterministic, legal initial placement generated using a simple row-wise strategy. 
    This serves as a reference point for comparison and ensures all blocks are placed without overlaps or boundary violations.
        The baseline uses a Smart Wall-Aware strategy with an ML Agent:
Logic: 
1. Environment sorts blocks by Difficulty (or inflexibility)
2. Environment proposes 'Smart Candidates' (Corners + Neighbors).
3. ML AGENT evaluates candidates based on physics features such as wall attraction, wire minimization, and thermal repulsion.
4. Environment strictly forbids overlaps between blocks, and out-of-bounds (Fallback to Grid Search).
    
**AI-Assisted Simulated Annealing Exploration:** The optimizer refines this layout by exploring the solution space stochastically. It accepts "worse" moves early on (High Temp) to escape local optima, then converges to a precise solution (Low Temp) using three move types: 
    
 * **Displacement:** Moving a single block to a new coordinate.
 * **Swap:** Exchanging positions of two blocks.
* **Rotation:** Rotating a block 90 degrees. Each move is evaluated against the cost function, 
 and moves are accepted probabilistically based on temperature and cost improvement.
    
 **Legal Moves and Best-Solution Tracking:** All proposed moves are validated to ensure no overlaps or boundary violations. 
 If a move reduces the cost (Reward > 0), the agent updates its Q-Table. Over time, it might learn that Swapping is great at high temperatures (to reorganize the board), while Displacement is better at low temperatures (for fine-tuning).
 """)

# -----------------------------
# 1. Physics Engine Configuration (Explainability)
# -----------------------------
with st.expander("🛠️ Solver Configuration & Physics Weights", expanded=True):
    c1, c2, c3 = st.columns(3)

    c1.metric("Wall Attraction", f"{CENTER_PENALTY_WEIGHT:.0f}", help="Force pushing heavy blocks to boundaries")
    c2.metric("Overlap Penalty", "1.0e4", help="Strict constraint against block collisions")
    c3.metric("Boundary Penalty", "1.0e4", help="Strict constraint against out-of-bounds placements")

    st.info(
        "**Engine Logic:** The solver uses a multi-objective cost function. "
        "It balances **Thermal Diffusion** (spreading heat) against **Wirelength** (keeping connections short), "
        "while strictly enforcing **Wall Attraction** for high-power macros."
    )

# -----------------------------
# Sidebar & Inputs
# -----------------------------
st.sidebar.header("Die Parameters")
die_width = st.sidebar.number_input("Die Width", min_value=50.0, value=120.0)
die_height = st.sidebar.number_input("Die Height", min_value=50.0, value=120.0)
run_button = st.sidebar.button("Run Optimization", type="primary")

# -----------------------------
# Block Table (20-Block Config for Wall Attraction)
# -----------------------------
st.subheader("Blocks")
st.caption("Power values mapped to realistic Watts based on HotSpot 'ev6' (Alpha 21364) profile.")

block_df = st.data_editor(
    pd.DataFrame([
        # --- THE HEAVYWEIGHTS (EV6 Execution Cores: High Power Density) ---
        # "Power 3" -> ~25W (IntExec, FPAdd clusters)
        {"block_id": "S7",  "role": "CPU_Cluster", "width": 28.0, "height": 28.0, "power": 25.0},
        {"block_id": "S4",  "role": "GPU_Core",    "width": 28.0, "height": 28.0, "power": 25.0},
        {"block_id": "S13", "role": "PCIe_Root",   "width": 25.0, "height": 25.0, "power": 20.0},
        {"block_id": "S14", "role": "NPU_Engine",  "width": 25.0, "height": 25.0, "power": 20.0},

        # --- THE MEMORY BACKBONE (EV6 L2/L3 Cache: Large Area, Low Power) ---
        # "Power 1" -> ~2W (Leakage/Background)
        {"block_id": "S2",  "role": "L3_Cache",    "width": 20.0, "height": 20.0, "power": 2.0},
        {"block_id": "S15", "role": "Sys_SRAM",    "width": 30.0, "height": 10.0, "power": 2.0},

        # --- THE PERIPHERAL WALLS (Long & Thin) ---
        {"block_id": "S6",  "role": "NoC_Left",    "width": 8.0,  "height": 70.0, "power": 1.5},
        {"block_id": "S12", "role": "NoC_Right",   "width": 8.0,  "height": 70.0, "power": 1.5},
        {"block_id": "S8",  "role": "DDR_Top",     "width": 60.0, "height": 8.0,  "power": 8.0},
        {"block_id": "S11", "role": "DDR_Bot",     "width": 60.0, "height": 8.0,  "power": 8.0},

        # --- MEDIUM LOGIC BLOCKS (EV6 Instruction Queues/Maps) ---
        # "Power 2" -> ~10W (Active Logic)
        {"block_id": "S5",  "role": "DSP_Unit",    "width": 15.0, "height": 15.0, "power": 10.0},
        {"block_id": "S10", "role": "Video_Enc",   "width": 15.0, "height": 15.0, "power": 12.0},
        {"block_id": "S16", "role": "Modem_5G",    "width": 18.0, "height": 12.0, "power": 10.0},
        {"block_id": "S17", "role": "ISP_Cam",     "width": 12.0, "height": 18.0, "power": 10.0},

        # --- SMALL CONTROLLERS (Fillers / Peripherals) ---
        # Very low power (<1W)
        {"block_id": "S3",  "role": "Power_Mgt",   "width": 10.0, "height": 10.0, "power": 0.5},
        {"block_id": "S1",  "role": "Sensors",     "width": 10.0, "height": 10.0, "power": 0.5},
        {"block_id": "S9",  "role": "Security",    "width": 12.0, "height": 12.0, "power": 1.0},
        {"block_id": "S18", "role": "Audio_Sub",   "width": 10.0, "height": 10.0, "power": 1.0},
        {"block_id": "S19", "role": "USB_Ctrl",    "width": 10.0, "height": 10.0, "power": 1.5},
        {"block_id": "S20", "role": "GPIO_Mux",    "width": 15.0, "height": 5.0,  "power": 0.5},
    ]),
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "width": st.column_config.NumberColumn("Width", min_value=1.0, required=True),
        "height": st.column_config.NumberColumn("Height", min_value=1.0, required=True),
        "power": st.column_config.NumberColumn("Power (Watts)", min_value=0.0, max_value=100.0, format="%.1f W"),
    }
)

st.subheader("Nets")

# We programmatically generate the star topology for the dataframe
# S2 is the central hub.
central_hub = "S2"
# All other blocks connect to it
peripherals = [
    "S1", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", 
    "S11", "S12", "S13", "S14", "S15", "S16", "S17", "S18", "S19", "S20"
]

# Create the list of connections
net_data = []
for i, block in enumerate(peripherals):
    # Higher weights for high-performance blocks (S4, S7, S13, S14)
    # to pull them tighter than the small peripherals.
    if block in ["S4", "S7", "S13", "S14"]:
        w = 25.0 
    else:
        w = 10.0
        
    net_data.append({
        "net_id": f"N_STAR_{i}", 
        "block_a": central_hub, 
        "block_b": block, 
        "weight": w
    })

# Add a few ring connections so the outer blocks aren't totally isolated from each other
ring_connections = [
    {"net_id": "N_RING_1", "block_a": "S7", "block_b": "S4", "weight": 15.0},
    {"net_id": "N_RING_2", "block_a": "S4", "block_b": "S14", "weight": 15.0},
    {"net_id": "N_RING_3", "block_a": "S14", "block_b": "S13", "weight": 15.0},
    {"net_id": "N_RING_4", "block_a": "S13", "block_b": "S7", "weight": 15.0},
]

net_df = st.data_editor(
    pd.DataFrame(net_data + ring_connections),
    num_rows="dynamic",
    use_container_width=True
)

# -----------------------------
# Compilers (Helpers)
# -----------------------------
def compile_blocks(block_df):
    rows = []
    for _, r in block_df.iterrows():
        rows.append({
            "id": str(r["block_id"]),
            "width": float(r["width"]),
            "height": float(r["height"]),
            "power": float(r["power"]),  # Changed from int to float for Watts
            "heat": 0,  # [MODIFIED] Hardcoded to 0 since input removed
            "role": str(r["role"]) 
        })
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf

def compile_nets(net_df):
    net_map = defaultdict(list)
    weights = {}
    for _, r in net_df.iterrows():
        net = str(r["net_id"])
        net_map[net].append(str(r["block_a"]))
        net_map[net].append(str(r["block_b"]))
        weights[net] = float(r["weight"])
    rows = []
    for net, blocks in net_map.items():
        rows.append({
            "name": net,
            "blocks": ",".join(sorted(set(blocks))),
            "weight": weights[net],
        })
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf

# -----------------------------
# Execution Logic
# -----------------------------
if run_button:
    die = Die(die_width, die_height)
    
    # Load data from the DataFrames defined above
    blocks = load_blocks_csv(compile_blocks(block_df))
    nets = load_nets_csv(compile_nets(net_df))

    # --- 1. Smart Baseline with Error Check ---
    baseline = baseline_place(blocks, die, nets)
    
    # Check if baseline placement failed
    if baseline is None:
        st.error("⚠️ **Die Area Too Small!**")
        st.warning(
            "The current die dimensions are insufficient to place all blocks without overlap. "
            "Please **increase the die width and/or height** in the sidebar and try again."
        )
        st.info(
            f"💡 **Suggestion:** Try increasing die dimensions to at least "
            f"{die_width * 1.5:.0f} x {die_height * 1.5:.0f} or larger."
        )
        st.stop()  # Stops execution here, preventing optimization from running
    
    base_orient = {b.id: False for b in blocks}
    base_cost = total_cost(baseline, base_orient, blocks, nets, die)

    # --- Show Baseline Layout ---
    st.divider()
    st.subheader("📊 Baseline Layout")
    st.markdown("**Smart Baseline** (Initial Legal Placement)")
    
    # Helper to safely get 'role' or fallback to 'id'
    def get_label(b):
        return getattr(b, "role", b.id)

    label_map = {b.id: get_label(b) for b in blocks}
    
    # Show baseline visualization
    col_base1, col_base2 = st.columns([2, 1])
    with col_base1:
        st.pyplot(plot_placement(
            baseline, 
            blocks, 
            die, 
            nets=nets,
            title="Baseline Placement", 
            orientations=base_orient, 
            labels=label_map
        ))
    with col_base2:
        st.metric("Baseline Cost", f"{base_cost:,.0f}", help="Cost of the initial smart placement")
        
        # Show baseline cost breakdown
        c_wire_base = compute_hpwl_wirelength(baseline, base_orient, blocks, nets)
        c_over_base = compute_overlap_penalty(baseline, base_orient, blocks)
        c_therm_base = compute_thermal_penalty(baseline, base_orient, blocks)
        c_bound_base = compute_boundary_penalty(baseline, base_orient, blocks, die)
        c_cent_base = compute_center_penalty(baseline, base_orient, blocks, die)
        
        st.markdown("**Baseline Cost Breakdown:**")
        st.write(f"Wirelength: {c_wire_base:,.0f}")
        st.write(f"Overlap: {c_over_base:,.0f}")
        st.write(f"Thermal: {c_therm_base:,.0f}")
        st.write(f"Boundary: {c_bound_base:,.0f}")
        st.write(f"Wall Attraction: {c_cent_base:,.0f}")

    # --- 2. Live Optimization Dashboard ---
    st.divider()
    st.subheader("🚀 Optimization Progress")
    
    # Store results from all three runs
    all_runs = []
    temp_configs = [1000.0, 2000.0, 3000.0]
    
    for run_idx, initial_temp in enumerate(temp_configs, 1):
        st.markdown(f"### Run {run_idx}/3 - Initial Temperature: {initial_temp}")
        
        # Dashboard Layout
        prog_bar = st.progress(0)
        status_col1, status_col2, status_col3, status_col4 = st.columns(4)
        
        live_temp = status_col1.empty()
        live_cost = status_col2.empty()
        live_acc = status_col3.empty()
        live_status = status_col4.empty()
        
        # --- Callback Function ---
        def sa_callback(step, temp, cost, acceptance):
            progress = min(1.0, step / 150)
            prog_bar.progress(progress)
            
            live_temp.metric("Temperature (T)", f"{temp:.2f}", help="Current annealing temperature")
            live_cost.metric("Current Cost", f"{cost:,.0f}", help="Cost of the current placement")
            live_acc.metric("Acceptance Rate", f"{acceptance:.1%}", help="Proportion of accepted moves")
            
            if temp > 100:
                live_status.info("Phase: Exploration (High Temp)")
            elif temp > 1:
                live_status.warning("Phase: Refinement (Med Temp)")
            else:
                live_status.success("Phase: Convergence (Low Temp)")
            
            time.sleep(0.01)

        # Run Engine
        r_place, r_cost, r_hist, r_orient = simulated_annealing(
            blocks, nets, die,
            initial_temperature=initial_temp,
            alpha=0.95,
            k_steps=50,   
            callback=sa_callback
        )
        
        prog_bar.progress(1.0)
        
        # Store this run's results
        all_runs.append({
            'temp': initial_temp,
            'placement': r_place,
            'cost': r_cost,
            'history': r_hist,
            'orientations': r_orient
        })
        
        # Show this run's result
        st.markdown(f"**Run {run_idx} Complete** - Final Cost: {r_cost:,.0f}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Run {run_idx} Layout**")
            st.pyplot(plot_placement(
                r_place, 
                blocks, 
                die, 
                nets=nets,
                title=f"Run {run_idx} (T={initial_temp})", 
                orientations=r_orient, 
                labels=label_map
            ))
        with col2:
            # Show cost breakdown for this run
            c_wire = compute_hpwl_wirelength(r_place, r_orient, blocks, nets)
            c_over = compute_overlap_penalty(r_place, r_orient, blocks)
            c_therm = compute_thermal_penalty(r_place, r_orient, blocks)
            c_bound = compute_boundary_penalty(r_place, r_orient, blocks, die)
            c_cent = compute_center_penalty(r_place, r_orient, blocks, die)
            
            st.markdown(f"**Run {run_idx} Cost Breakdown**")
            st.write(f"Wirelength: {c_wire:,.0f}")
            st.write(f"Overlap: {c_over:,.0f}")
            st.write(f"Thermal: {c_therm:,.0f}")
            st.write(f"Boundary: {c_bound:,.0f}")
            st.write(f"Wall Attraction: {c_cent:,.0f}")
        
        st.divider()
    
    # --- 3. Select Best Run ---
    best_run = min(all_runs, key=lambda x: x['cost'])
    r_place = best_run['placement']
    r_cost = best_run['cost']
    r_hist = best_run['history']
    r_orient = best_run['orientations']
    
    st.success(f"🏆 **Best Result**: Run with T={best_run['temp']} (Cost: {r_cost:,.0f})")
    
    
    # --- 4. Results & Explainability --- 
    
    
    
    
    st.divider()
    st.subheader("Optimization Results")
    st.markdown("This section summarizes the final optimized layout and provides detailed insights into the cost function components.")
    

    # Helper to safely get 'role' or fallback to 'id'
    def get_label(b):
        return getattr(b, "role", b.id)

    label_map = {b.id: get_label(b) for b in blocks}

    # Visual Comparison
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Smart Baseline** (Initial Legal Placement)")
        st.pyplot(plot_placement(
            baseline, 
            blocks, 
            die, 
            nets=nets,  # <--- ADDED THIS LINE
            title="Baseline", 
            orientations=base_orient, 
            labels=label_map
        ))
    with col2:
        st.markdown("**Optimized Layout** (Physics-Aware)")
        st.pyplot(plot_placement(
            r_place, 
            blocks, 
            die, 
            nets=nets,  # <--- ADDED THIS LINE
            title="Final Layout", 
            orientations=r_orient, 
            labels=label_map
        ))

    # --- 4. Cost Breakdown (The "Why") ---
    st.subheader("Cost Function Breakdown")
    st.markdown("This chart explains **why** the AI chose this layout. Lower is better.")
    
    # Calculate components
    c_wire = compute_hpwl_wirelength(r_place, r_orient, blocks, nets)
    c_over = compute_overlap_penalty(r_place, r_orient, blocks)
    c_therm = compute_thermal_penalty(r_place, r_orient, blocks)
    c_bound = compute_boundary_penalty(r_place, r_orient, blocks, die)
    c_cent = compute_center_penalty(r_place, r_orient, blocks, die)



    # Display Metrics with Delta arrows
    m1, m2, m3 = st.columns(3)
    m1.metric("Baseline Cost", f"{base_cost:,.0f}", help="Cost of the initial smart placement")
    m2.metric("Optimized Cost", f"{r_cost:,.0f}", help="Final cost after annealing")
    
    imp_percent = ((base_cost - r_cost) / base_cost * 100) if base_cost > 0 else 0.0
    improvement = base_cost - r_cost
    m3.metric(
        label="Improvement", 
        value=f"{imp_percent:.1f}%", 
        delta=f"-{improvement:,.0f} (Saved)",
        delta_color="inverse"
    )

    # Calculate Total for Percentages
    total_components = c_wire + c_over + c_therm + c_bound + c_cent
    
    def fmt_pct(val):
        pct = (val / total_components * 100) if total_components > 0 else 0.0
        return f"{pct:.1f}% of Total Cost"

    # Prepare Data
    cost_data = pd.DataFrame({
        "Component": ["Wirelength", "Overlap", "Thermal", "Boundary", "Wall Attraction"],
        "Raw Cost": [c_wire, c_over, c_therm, c_bound, c_cent],
        "Description": [
            fmt_pct(c_wire),
            fmt_pct(c_over),
            fmt_pct(c_therm),
            fmt_pct(c_bound),
            fmt_pct(c_cent)
        ]
    })
    
    # Detailed Breakdown
    st.dataframe(
        cost_data.style.format({"Raw Cost": "{:.2f}"}), 
        use_container_width=True,
        hide_index=True
    )
    
    # --- 4. Final Coordinates & Export ---
    st.divider()
    st.subheader("💾 Export Results")

    # 1. Compile Data
    coord_data = []
    for block in blocks:
        if block.id in r_place:
            x, y = r_place[block.id]
            coord_data.append({
                "Block ID": block.id,
                "X (Bottom-Left)": round(x, 2),
                "Y (Bottom-Left)": round(y, 2),
                "Width": block.width,
                "Height": block.height,
                "Power (W)": block.power
            })
    
    # 2. Create DataFrame
    df_coords = pd.DataFrame(coord_data).sort_values(by="Block ID")

    # 3. Display Interactive Table
    st.caption("Final placed coordinates for all macros.")
    st.dataframe(
        df_coords,
        use_container_width=True,
        hide_index=True,
        column_config={
            "X (Bottom-Left)": st.column_config.NumberColumn(format="%.2f"),
            "Y (Bottom-Left)": st.column_config.NumberColumn(format="%.2f"),
        }
    )

    # 4. Download Button (The "Output" feature)
    csv = df_coords.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Download Coordinates (CSV)",
        data=csv,
        file_name="laiopt_placement.csv",
        mime="text/csv",
        type="primary"
    )
    # 5. save coords to data folder
    df_coords.to_csv(r'C:\Users\varun\Desktop\Via2\LAIOpt\laiopt\data\laiopt_placement.csv', index=False)