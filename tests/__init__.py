"""
Test package marker.

Makes the top-level `tests` directory a Python package so that relative
imports inside test modules (e.g., `.hardware.unit_op_hardware`) work
reliably across different environments.
"""

