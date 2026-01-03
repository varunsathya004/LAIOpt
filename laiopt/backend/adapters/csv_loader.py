"""
Converts CSV input into internal models.

This module handles:
- Loading macro blocks from CSV (ID, width, height, power level, heat level)
- Loading connectivity/nets from CSV (with weights)
- Loading die definition from CSV or configuration
- Validating and converting CSV data into Block, Net, and Die objects

This is the input adapter layer between file system and core models.
"""

