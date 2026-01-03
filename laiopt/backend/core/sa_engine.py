"""
Simulated Annealing optimizer.

This module implements the optimization engine using:
- Legal move generation that respects constraints
- Acceptance logic based on cost comparison and controlled randomness
- Deterministic behavior aside from documented controllable randomness
- Temperature schedule management

The optimizer uses cost functions to iteratively improve macro placement.
"""

