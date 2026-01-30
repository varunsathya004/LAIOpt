"""

Smart Wall-Aware Baseline Placer (Strict No-Overlap).

Logic:

1. Sorts blocks by Difficulty (Size + Aspect Ratio + Nets + Heat).

2. Tries 'Smart' Candidates first (Corners + Adjacent) to optimize Physics.

3. If Smart Candidates are blocked, performs a 'Grid Search' to find ANY valid empty spot.

4. STRICTLY forbids overlaps.

"""

from typing import List, Tuple, Dict

from collections import defaultdict

import math

from laiopt.backend.core.models import Block, Die, Net



Placement = Dict[str, Tuple[float, float]]



def baseline_place(blocks: List[Block], die: Die, nets: List[Net] = None) -> Placement:

    """

    Places blocks using a Multi-Objective Heuristic.

    GUARANTEE: No overlaps. If the smart heuristic fails, it scans for a free spot.

    """

   

    # --- 1. Pre-Computation (Connectivity & Scores) ---

    adj_map = defaultdict(lambda: defaultdict(float))

    if nets:

        for net in nets:

            for i in range(len(net.blocks)):

                u = net.blocks[i]

                for j in range(i + 1, len(net.blocks)):

                    v = net.blocks[j]

                    adj_map[u][v] += net.weight

                    adj_map[v][u] += net.weight



    connectivity_score = {b.id: sum(adj_map[b.id].values()) for b in blocks}



    def get_inflexibility_score(b: Block) -> float:

        # [UPDATED] Heuristic for "Difficulty":

        # 1. Area: Big blocks are hard.

        # 2. Power: Hot blocks need specific spots (walls).

        # 3. Max Dimension: Long/Skinny blocks (60x8) are VERY hard to fit later.

        #    We weigh MaxDim heavily to prevent fragmentation.

        area_score = b.width * b.height 

        power_score = b.power *10

        aspect_score = max(b.width, b.height) * 10

       

        return area_score + connectivity_score.get(b.id, 0.0) * 10 + power_score + aspect_score


        



    # Sort descending (Hardest blocks first)

    sorted_blocks = sorted(blocks, key=get_inflexibility_score, reverse=True)

   

    # --- 2. Placement State ---

    placement = {}

    # occupied_spaces stores: (x, y, w, h, power, id)

    occupied_spaces = []



    def check_overlap(nx, ny, nw, nh, occupied):

        """Returns True if the proposed rect (nx, ny, nw, nh) overlaps any existing block."""

        for (ox, oy, ow, oh, _, _) in occupied:

            # Standard AABB overlap check (Strict < and >)

            # Using strict inequality allows touching edges

            if (nx < ox + ow and nx + nw > ox and

                ny < oy + oh and ny + nh > oy):

                return True

        return False



    def find_fallback_spot(b_width, b_height):

        """

        Emergency Grid Search: Scans the die to find the first available non-overlapping spot.

        """

        # [UPDATED] Step size set to 1.0 for precision.

        # Coarse steps (like width/4) might skip over valid narrow gaps.

        step_x = 1.0

        step_y = 1.0

       

        curr_y = 0.0

        while curr_y <= die.height - b_height:

            curr_x = 0.0

            while curr_x <= die.width - b_width:

                if not check_overlap(curr_x, curr_y, b_width, b_height, occupied_spaces):

                    return (curr_x, curr_y)

                curr_x += step_x

            curr_y += step_y

        return None



    # Weights for the Multi-Objective Heuristic

    ALPHA_WALL = 1000   

    BETA_WIRE = 5.0        

    GAMMA_THERMAL = 5000.0



    for block in sorted_blocks:

        w, h = block.width, block.height

        valid_candidates = []

       

        # --- A. Candidate Generation (Smart Spots) ---

        corners = [

            (0.0, 0.0),                    

            (0.0, die.height - h),          

            (die.width - w, 0.0),          

            (die.width - w, die.height - h)

        ]

       

        adjacent = []

        for (ox, oy, ow, oh, _, _) in occupied_spaces:

            adjacent.append((ox + ow, oy))       # Right

            adjacent.append((ox, oy + oh))       # Top

            adjacent.append((ox - w, oy))        # Left

            adjacent.append((ox, oy - h))        # Bottom

       

        raw_candidates = corners + adjacent

       

        # --- B. Strict Filter ---

        for cx, cy in raw_candidates:

            # 1. Boundary Check

            if cx < 0 or cy < 0 or cx + w > die.width or cy + h > die.height:

                continue

            # 2. Overlap Check (Strict)

            if not check_overlap(cx, cy, w, h, occupied_spaces):

                valid_candidates.append((cx, cy))



        # --- C. Selection (If Smart Candidates Exist) ---

        final_pos = None

       

        if valid_candidates:

            best_score = float('inf')

            best_pos = valid_candidates[0]



            for (cx, cy) in valid_candidates:

                # 1. Wall Cost

                d_left = cx

                d_right = die.width - (cx + w)

                d_bottom = cy

                d_top = die.height - (cy + h)

                dist_wall = min(d_left, d_right, d_bottom, d_top)

               

                cost_wall = dist_wall * ALPHA_WALL



                # 2. Wire & Thermal Cost (vs Placed Neighbors)

                cost_wire = 0.0

                cost_thermal = 0.0

                curr_cx, curr_cy = cx + w/2, cy + h/2



                for (ox, oy, ow, oh, opower, oid) in occupied_spaces:

                    other_cx, other_cy = ox + ow/2, oy + oh/2

                    dist = abs(curr_cx - other_cx) + abs(curr_cy - other_cy)

                    dist = max(dist, 1.0)



                    # Wire Attraction

                    weight = adj_map[block.id].get(oid, 0.0)

                    if weight > 0:

                        cost_wire += dist * weight



                    # Thermal Repulsion

                    if block.power > 0 and opower > 0:

                        cost_thermal += (block.power * opower) / (dist ** 2)



                total_score = cost_wall + (cost_wire * BETA_WIRE) + (cost_thermal * GAMMA_THERMAL)



                if total_score < best_score:

                    best_score = total_score

                    best_pos = (cx, cy)

                elif total_score == best_score:

                    if (cx + cy) < (best_pos[0] + best_pos[1]): # Tie-break

                        best_pos = (cx, cy)

           

            final_pos = best_pos



        # --- D. FALLBACK (If Smart Candidates Failed) ---

        # --- D. FALLBACK (If Smart Candidates Failed) ---
        else:
            # The heuristic got stuck (no corners/neighbors fit).
            # We MUST scan the die for any valid free space.
            fallback_pos = find_fallback_spot(w, h)
           
            if fallback_pos:
                final_pos = fallback_pos
            else:
                # If even grid search fails, the die is physically too small or fragmented.
                # Return None to signal failure instead of raising error
                return None

        # --- E. Finalize Placement ---
        placement[block.id] = final_pos
        occupied_spaces.append((final_pos[0], final_pos[1], w, h, block.power, block.id))

    return placement


        