"""
Hybrid Simulated Annealing Engine with RL Agent (Hyper-Heuristic).
Updated: Integrates 3-State Q-Learning Agent to guide move selection.
"""

import math
import random
import numpy as np
from typing import Dict, Tuple, List, Callable, Optional

from laiopt.backend.core.models import Block, Net, Die
from laiopt.backend.core.baseline import baseline_place
from laiopt.backend.core.cost import (
    total_cost, 
    get_effective_dims
)

Placement = Dict[str, Tuple[float, float]]
Orientations = Dict[str, bool]

# --- Manufacturing Grid ---
PLACEMENT_PITCH = 1.0 

def snap_to_grid(val: float, pitch: float) -> float:
    """Snaps a coordinate to the nearest valid grid line."""
    return round(val / pitch) * pitch

# --- RL AGENT CLASS ---
class RLAgent:
    def __init__(self, actions=["displace", "swap", "rotate"], learning_rate=0.1, discount=0.9):
        self.actions = actions
        self.lr = learning_rate
        self.gamma = discount
        self.epsilon = 0.2  # 20% exploration, 80% exploitation
        
        # Q-Table: 3 States (Rows) x 3 Actions (Columns)
        self.q_table = np.zeros((3, len(actions))) 

    def get_state(self, current_temp, initial_temp):
        """Discretize temperature into 3 simple states."""
        ratio = current_temp / initial_temp
        if ratio > 0.66:
            return 0  # High Temp (Exploration Phase)
        elif ratio > 0.33:
            return 1  # Med Temp (Transition)
        else:
            return 2  # Low Temp (Refinement)

    def choose_action(self, state, rng):
        """Epsilon-Greedy Policy"""
        if rng.random() < self.epsilon:
            return rng.choice(range(len(self.actions))) # Explore
        else:
            # Pick action with highest Q-value for this state
            values = self.q_table[state]
            if np.all(values == values[0]):
                return rng.choice(range(len(self.actions)))
            return np.argmax(values)

    def learn(self, state, action_idx, reward, next_state):
        """Update Q-Value using Bellman Equation"""
        old_value = self.q_table[state, action_idx]
        next_max = np.max(self.q_table[next_state])
        
        new_value = (1 - self.lr) * old_value + self.lr * (reward + self.gamma * next_max)
        self.q_table[state, action_idx] = new_value

# --- MAIN ENGINE ---

def simulated_annealing(
    blocks: List[Block],
    nets: List[Net],
    die: Die,
    *,
    initial_temperature: float = 1000.0,
    final_temperature: float = 0.001,
    alpha: float = 0.95,
    k_steps: int = 100, 
    move_scale: float = 20.0,
    random_seed = 42,
    callback: Optional[Callable[[int, float, float, float], None]] = None  
) -> Tuple[Placement, float, List[float], Orientations]:
    
    rng = random.Random(random_seed) if random_seed is not None else random.Random()
    
    # 1. Initialize AI Agent
    agent = RLAgent()

    # 2. Initialization
    current_place = baseline_place(blocks, die, nets)
    
    # Force Initial Baseline to Grid
    for bid in current_place:
        bx, by = current_place[bid]
        current_place[bid] = (snap_to_grid(bx, PLACEMENT_PITCH), 
                              snap_to_grid(by, PLACEMENT_PITCH))

    current_orient = {b.id: False for b in blocks}
    
    # [UPDATED] Calculate initial cost (No normalization factors needed)
    current_cost = total_cost(current_place, current_orient, blocks, nets, die)

    best_place = dict(current_place)
    best_orient = dict(current_orient)
    best_cost = current_cost
    cost_history = [current_cost]

    temperature = initial_temperature
    block_map = {b.id: b for b in blocks}
    block_ids = list(block_map.keys())
    
    rejection_rate = 0.0
    iteration_counter = 0

    # Optimization Loop
    while (rejection_rate < 0.99) and (temperature > final_temperature):
        
        reject_count = 0
        state_idx = agent.get_state(temperature, initial_temperature)
        
        # Inner Markov Chain
        for _ in range(k_steps):
            next_place = dict(current_place)
            next_orient = dict(current_orient)
            
            # --- AI DECISION ---
            action_idx = agent.choose_action(state_idx, rng)
            move_type = agent.actions[action_idx] 
            
            # --- EXECUTE MOVE ---
            if move_type == "displace": 
                block_id = rng.choice(block_ids)
                block = block_map[block_id]
                x, y = current_place[block_id]
                scale = move_scale * (temperature / initial_temperature) + 1.0
                raw_x = x + rng.uniform(-scale, scale)
                raw_y = y + rng.uniform(-scale, scale)

                snapped_x = snap_to_grid(raw_x, PLACEMENT_PITCH)
                snapped_y = snap_to_grid(raw_y, PLACEMENT_PITCH)
                w, h = get_effective_dims(block, current_orient)
                
                max_x = snap_to_grid(die.width - w, PLACEMENT_PITCH)
                max_y = snap_to_grid(die.height - h, PLACEMENT_PITCH)
                
                safe_x = max(0.0, min(snapped_x, max_x))
                safe_y = max(0.0, min(snapped_y, max_y))
                
                next_place[block_id] = (safe_x, safe_y)

            elif move_type == "swap":
                if len(block_ids) < 2: continue
                b1, b2 = rng.sample(block_ids, 2)
                next_place[b1], next_place[b2] = current_place[b2], current_place[b1]
                
                # Clamp check
                for bid in [b1, b2]:
                    bx, by = next_place[bid]
                    bw, bh = get_effective_dims(block_map[bid], current_orient)
                    max_x = snap_to_grid(die.width - bw, PLACEMENT_PITCH)
                    max_y = snap_to_grid(die.height - bh, PLACEMENT_PITCH)
                    safe_x = max(0.0, min(bx, max_x))
                    safe_y = max(0.0, min(by, max_y))
                    next_place[bid] = (safe_x, safe_y)

            elif move_type == "rotate":
                block_id = rng.choice(block_ids)
                next_orient[block_id] = not current_orient[block_id]
                rx, ry = current_place[block_id]
                rw, rh = get_effective_dims(block_map[block_id], next_orient)
                
                max_x = snap_to_grid(die.width - rw, PLACEMENT_PITCH)
                max_y = snap_to_grid(die.height - rh, PLACEMENT_PITCH)
                
                safe_x = max(0.0, min(rx, max_x))
                safe_y = max(0.0, min(ry, max_y))
                next_place[block_id] = (safe_x, safe_y)

            # --- EVALUATE ---
            # [UPDATED] Calculate new cost (No normalization factors)
            new_cost = total_cost(next_place, next_orient, blocks, nets, die)
            delta_cost = new_cost - current_cost

            # --- AI LEARNING SIGNAL ---
            reward = -(delta_cost) / 100.0
            reward = max(-10.0, min(10.0, reward))
            
            agent.learn(state_idx, action_idx, reward, state_idx)

            # --- METROPOLIS ACCEPTANCE ---
            accepted = False
            if delta_cost <= 0.0:
                accepted = True
            else:
                prob = math.exp(-delta_cost / temperature)
                if rng.random() < prob:
                    accepted = True

            if accepted:
                current_place = next_place
                current_orient = next_orient
                current_cost = new_cost
                if current_cost < best_cost:
                    best_place = dict(current_place)
                    best_orient = dict(current_orient)
                    best_cost = current_cost
            else:
                reject_count += 1
                
        # --- UPDATE STATS ---
        rejection_rate = reject_count / k_steps
        cost_history.append(current_cost)
        temperature *= alpha
        iteration_counter += 1
        
        if callback:
            callback(iteration_counter, temperature, current_cost, 1.0 - rejection_rate)
        
        if len(cost_history) > 8000: break

    return best_place, best_cost, cost_history, best_orient