"""
Visualization utilities for macro placement.
Updated: Adds Wire Visualization (Flylines) and Dynamic Power Heat Map.
"""

from typing import Dict, Tuple, List, Optional
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle, Circle

from laiopt.backend.core.models import Block, Die, Net

Placement = Dict[str, Tuple[float, float]]
Orientations = Dict[str, bool]

def plot_placement(
    placement: Placement,
    blocks: List[Block],
    die: Die,
    nets: List[Net] = None,  # [UPDATED] Added nets argument
    title: str = "Placement",
    orientations: Optional[Orientations] = None,
    labels: Optional[Dict[str, str]] = None
):
    """
    Plot a macro placement with dynamic thermal coloring and wire flylines.
    """
    fig, ax = plt.subplots(figsize=(6, 6))

    # Margin and Outline
    margin = 0.05 * min(die.width, die.height)
    ax.add_patch(
        Rectangle((0, 0), die.width, die.height, 
                  fill=False, edgecolor="black", linewidth=2, linestyle="--")
    )
    ax.set_xlim(-margin, die.width + margin)
    ax.set_ylim(-margin, die.height + margin)
    ax.set_aspect('equal')
    ax.set_title(title)

    # --- 1. Setup Dynamic Color Normalization ---
    all_powers = [b.power for b in blocks]
    max_power = max(all_powers) if all_powers else 1.0
    norm = mcolors.Normalize(vmin=0.0, vmax=max_power)
    cmap = plt.cm.RdYlBu_r 

    # Helper: Track centers for wire drawing
    block_centers = {}

    # --- 2. Draw Blocks ---
    for block in blocks:
        if block.id not in placement:
            continue
            
        x, y = placement[block.id]
        
        # Rotation Logic
        is_rotated = orientations.get(block.id, False) if orientations else False
        current_w = block.height if is_rotated else block.width
        current_h = block.width if is_rotated else block.height

        # Calculate Center for Wires
        cx = x + current_w / 2.0
        cy = y + current_h / 2.0
        block_centers[block.id] = (cx, cy)

        # Dynamic Color
        color = cmap(norm(block.power))

        # Draw Block
        rect = Rectangle(
            (x, y), current_w, current_h,
            fill=True, facecolor=color, edgecolor="black", linewidth=1.0, alpha=0.9,
            zorder=10 # Keep blocks on top of wires
        )
        ax.add_patch(rect)
        
        # Labeling
        display_text = labels.get(block.id, block.id) if labels else block.id
        ax.text(
            cx, cy, display_text,
            ha="center", va="center", fontsize=7,
            color="black", weight="bold",
            clip_on=True, zorder=11
        )
# --- 3. Draw Wires (Flylines) ---
    if nets:
        # Sort nets so heavy ones are drawn LAST (on top of light ones)
        sorted_nets = sorted(nets, key=lambda n: n.weight)
        
        # Find max weight for normalization
        max_weight = sorted_nets[-1].weight if sorted_nets else 1.0
        
        for net in sorted_nets:
            points = []
            for b_id in net.blocks:
                if b_id in block_centers:
                    points.append(block_centers[b_id])
            
            if len(points) < 2:
                continue

            # Star Topology Centroid
            avg_x = sum(p[0] for p in points) / len(points)
            avg_y = sum(p[1] for p in points) / len(points)

            # --- MORE VISIBLE WIRES ---
            ratio = net.weight / max_weight
            
            # Three-tier system: High, Medium, Low
            if ratio > 0.7:
                # High-priority: Bold and prominent
                wire_color = "#E63946"  # Clean red
                alpha = 0.85
                lw = 2.5
                z_ord = 9
            elif ratio > 0.4:
                # Medium-priority: Clear and readable
                wire_color = "#457B9D"  # Steel blue
                alpha = 0.7
                lw = 1.8
                z_ord = 7
            else:
                # Low-priority: Still clearly visible
                wire_color = "#80B4BD"  # Medium blue-gray
                alpha = 0.55
                lw = 1.2
                z_ord = 5

            # Draw Lines
            for (bx, by) in points:
                ax.plot(
                    [avg_x, bx], [avg_y, by], 
                    color=wire_color, alpha=alpha, linewidth=lw, 
                    zorder=z_ord, linestyle="-"
                )
            
            # Centroid dot (only for high-priority nets)
            if ratio > 0.7:
                ax.add_patch(Circle(
                    (avg_x, avg_y), radius=0.7, 
                    color=wire_color, alpha=0.8, zorder=z_ord
                ))
    # --- 4. Add Colorbar ---
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([]) 
    cbar = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Power Density (Watts)', rotation=270, labelpad=15)

    return fig