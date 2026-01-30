"""
Cost functions for placement evaluation.
OPTIMIZED: Faster thermal penalty computation with distance cutoff.
TUNED: Rebalanced to allow Wire Attraction to overcome Thermal Repulsion.
"""

import math
from typing import Dict, Tuple, List
from laiopt.backend.core.models import Block, Net, Die

# --- Optimization Weights & Constants ---
OVERLAP_WEIGHT = 1e4           
BOUNDARY_PENALTY = 1e4         
THERMAL_PENALTY_WEIGHT = 1.0
# --- REBALANCED PHYSICS ---

THERMAL_SPREAD_K = 100.0       
MAX_SAFE_TEMP = 100.0          

# --- CENTER PENALTY ---
CENTER_PENALTY_WEIGHT = 2500.0 

# --- THERMAL OPTIMIZATION ---
# Pre-compute thermal decay threshold
# Beyond this distance, thermal contribution is negligible (< 0.01% of power)
# exp(-9.21) ≈ 0.0001, so we use sqrt(K * 9.21) as cutoff
THERMAL_CUTOFF_DIST = math.sqrt(THERMAL_SPREAD_K * 9.21)  # ≈ 30.35 units

Placement = Dict[str, Tuple[float, float]]
Orientations = Dict[str, bool]


def get_effective_dims(block: Block, orientations: Orientations) -> Tuple[float, float]:
    is_rotated = orientations.get(block.id, False)
    if is_rotated:
        return block.height, block.width
    return block.width, block.height


def get_center(
    x: float, y: float, block: Block, orientations: Orientations
) -> Tuple[float, float]:
    w, h = get_effective_dims(block, orientations)
    return x + w / 2.0, y + h / 2.0


def compute_hpwl_wirelength(
    placement: Placement,
    orientations: Orientations,
    blocks: List[Block],
    nets: List[Net],
) -> float:
    """Compute weighted HPWL wirelength."""
    block_dict = {b.id: b for b in blocks}
    total_length = 0.0

    for net in nets:
        xs: List[float] = []
        ys: List[float] = []

        for block_id in net.blocks:
            if block_id not in placement or block_id not in block_dict:
                continue

            block = block_dict[block_id]
            x, y = placement[block_id]
            cx, cy = get_center(x, y, block, orientations)
            
            xs.append(cx)
            ys.append(cy)

        if len(xs) > 1:
            hpwl = (max(xs) - min(xs)) + (max(ys) - min(ys))
            total_length += hpwl * net.weight

    return total_length


def compute_overlap_penalty(
    placement: Placement,
    orientations: Orientations,
    blocks: List[Block],
) -> float:
    """Compute overlap penalty using effective dimensions."""
    penalty = 0.0
    
    rects = []
    for block in blocks:
        if block.id in placement:
            x, y = placement[block.id]
            w, h = get_effective_dims(block, orientations)
            rects.append((x, y, w, h))
        else:
            rects.append(None)

    for i in range(len(rects)):
        if rects[i] is None: continue
        ax, ay, aw, ah = rects[i]
        ax2, ay2 = ax + aw, ay + ah

        for j in range(i + 1, len(rects)):
            if rects[j] is None: continue
            bx, by, bw, bh = rects[j]
            bx2, by2 = bx + bw, by + bh

            overlap_w = min(ax2, bx2) - max(ax, bx)
            overlap_h = min(ay2, by2) - max(ay, by)

            if overlap_w > 0.0 and overlap_h > 0.0:
                penalty += overlap_w * overlap_h * OVERLAP_WEIGHT

    return penalty


def compute_boundary_penalty(
    placement: Placement,
    orientations: Orientations,
    blocks: List[Block],
    die: Die,
) -> float:
    penalty = 0.0
    for block in blocks:
        if block.id not in placement: continue
        x, y = placement[block.id]
        w, h = get_effective_dims(block, orientations)

        # STRICT Check (Binary) for efficiency since SA handles clamping
        if (x < -0.01 or y < -0.01 or (x + w) > die.width + 0.01 or (y + h) > die.height + 0.01):
            penalty += BOUNDARY_PENALTY
    return penalty


def compute_thermal_penalty(
    placement: Placement,
    orientations: Orientations,
    blocks: List[Block],
) -> float:
    """
    Compute Thermal Penalty (Pairwise)
    
    """
    total_thermal_cost = 0.0
    
    # OPTIMIZATION 1: Pre-build list of heat-emitting blocks with their centers
    # Only blocks with power > 0 can contribute heat to others
    aggressors = []
    for block in blocks:
        if block.id in placement and block.power > 0:
            x, y = placement[block.id]
            cx, cy = get_center(x, y, block, orientations)
            aggressors.append((block, cx, cy))
    
    # Early exit if no heat sources
    if not aggressors:
        return 0.0
    
    for victim in blocks:
        if victim.id not in placement: 
            continue
        
        # Base temp from victim's own heat generation
        current_temp = victim.power * 10.0
        
        x, y = placement[victim.id]
        vx, vy = get_center(x, y, block, orientations)

        for aggressor, ax, ay in aggressors:
            # Skip self-heating
            if victim.id == aggressor.id: 
                continue
            
            # OPTIMIZATION 2: Quick Manhattan distance check first
            # Manhattan distance is always >= Euclidean distance
            # So if Manhattan > cutoff, we can skip without computing sqrt
            manhattan_dist = abs(vx - ax) + abs(vy - ay)
            if manhattan_dist > THERMAL_CUTOFF_DIST * 1.414:  # sqrt(2) factor for safety
                continue
            
            # OPTIMIZATION 3: Compute Euclidean distance squared
            dist_sq = (vx - ax)**2 + (vy - ay)**2
            
            # Skip if beyond thermal influence radius
            if dist_sq > THERMAL_CUTOFF_DIST**2:
                continue
            
            # Only compute exp() for blocks within thermal range
            transferred_heat = aggressor.power * math.exp(-dist_sq / THERMAL_SPREAD_K)
            current_temp += transferred_heat

        # Apply penalty only if temperature exceeds threshold
        if current_temp > MAX_SAFE_TEMP:
            violation = current_temp - MAX_SAFE_TEMP
            total_thermal_cost += (violation ** 2)

    return total_thermal_cost


def compute_center_penalty(
    placement: Placement,
    orientations: Orientations,
    blocks: List[Block],
    die: Die,
) -> float:
    """
    Pushes high-power blocks toward the periphery (Edge Attraction).
    Implements the "Power Delivery" constraint by penalizing blocks 
    that sit in the center of the die.
    """
    cx = die.width / 2.0
    cy = die.height / 2.0
    
    # Max possible distance (Center to Corner) - used for normalization
    max_dist = math.sqrt(cx**2 + cy**2)
    
    total_penalty = 0.0

    for block in blocks:
        if block.id not in placement: continue
        
        # Get block center
        x, y = placement[block.id]
        bx, by = get_center(x, y, block, orientations)
        
        # Calculate distance from die center
        dist_from_center = math.sqrt((bx - cx)**2 + (by - cy)**2)
        
        # INVERTED SCORE: 
        # If dist is 0 (at center) -> Score is 1.0 (Max Penalty)
        # If dist is max (at corner) -> Score is 0.0 (No Penalty)
        center_score = 1.0 - (dist_from_center / max_dist)
        
        # Weight by Block Power
        # High power blocks get pushed harder. Zero power blocks (fillers) are ignored.
        total_penalty += center_score * block.power

    return total_penalty * CENTER_PENALTY_WEIGHT


def total_cost(
    placement: Placement,
    orientations: Orientations,
    blocks: List[Block],
    nets: List[Net],
    die: Die,
) -> float:
    wl = compute_hpwl_wirelength(placement, orientations, blocks, nets)
    ov = compute_overlap_penalty(placement, orientations, blocks)
    bd = compute_boundary_penalty(placement, orientations, blocks, die)
    tm = compute_thermal_penalty(placement, orientations, blocks)
    cp = compute_center_penalty(placement, orientations, blocks, die)

    return wl + ov + bd + tm + cp