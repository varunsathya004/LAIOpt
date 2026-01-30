"""
Defines core data structures for the LAIOpt system.

This module contains:
- Block: Represents a macro block with ID, width, height, power level, heat level
- Net: Represents connectivity between blocks with weights
- Die: Represents the chip area with width and height dimensions

These models are the foundation for all placement and optimization logic.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class Block:
    """
    Represents a macro block.

    Attributes:
        id (str): Unique identifier for the block.
        width (float): Width of the block.
        height (float): Height of the block.
        power (float): Power level of the block.
        heat (float): Heat level of the block.
    """
    id: str
    width: float
    height: float
    power: float
    heat: float

    def __post_init__(self):
        if self.width <= 0:
            raise ValueError("Block width must be positive.")
        if self.height <= 0:
            raise ValueError("Block height must be positive.")
        if self.power < 0:
            raise ValueError("Block power must be non-negative.")
        if self.heat < 0:
            raise ValueError("Block heat must be non-negative.")


@dataclass
class Net:
    """
    Represents connectivity between blocks.

    Attributes:
        name (str): Net identifier.
        blocks (List[str]): List of connected block IDs.
        weight (float): Weight of the net.
    """
    name: str
    blocks: List[str]
    weight: float
    halo: float = 0.0 #default
    def __post_init__(self):
        if not self.blocks or not isinstance(self.blocks, list):
            raise ValueError("Net must connect at least one block.")
        if self.weight < 0:
            raise ValueError("Net weight must be non-negative.")


@dataclass
class Die:
    """
    Represents the chip area (die).

    Attributes:
        width (float): Width of the die.
        height (float): Height of the die.
    """
    width: float
    height: float

    def __post_init__(self):
        if self.width <= 0:
            raise ValueError("Die width must be positive.")
        if self.height <= 0:
            raise ValueError("Die height must be positive.")
