"""
Visualization utilities for macro placement.

This module provides safe, geometry-accurate plotting functions
for baseline and optimized placements.
"""

from typing import Dict, Tuple, List
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from laiopt.backend.core.models import Block, Die

Placement = Dict[str, Tuple[float, float]]


def plot_placement(
    placement: Placement,
    blocks: List[Block],
    die: Die,
    title: str = "Placement"
):
    """
    Plot a macro placement within the die.

    Args:
        placement (Placement): Block ID -> (x, y)
        blocks (List[Block]): Block definitions
        die (Die): Die dimensions
        title (str): Plot title
    """
    fig, ax = plt.subplots(figsize=(6, 6))

    # Draw die outline
    ax.add_patch(
        Rectangle(
            (0, 0),
            die.width,
            die.height,
            fill=False,
            edgecolor="black",
            linewidth=2
        )
    )

    # Draw blocks
    block_dict = {b.id: b for b in blocks}
    for block_id, (x, y) in placement.items():
        block = block_dict[block_id]
        rect = Rectangle(
            (x, y),
            block.width,
            block.height,
            fill=True,
            alpha=0.6
        )
        ax.add_patch(rect)
        ax.text(
            x + block.width / 2,
            y + block.height / 2,
            block_id,
            ha="center",
            va="center",
            fontsize=8
        )

    ax.set_xlim(0, die.width)
    ax.set_ylim(0, die.height)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(True, linestyle="--", alpha=0.3)

    return fig
