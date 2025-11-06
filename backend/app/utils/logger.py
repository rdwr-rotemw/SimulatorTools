"""
Simple logger utility (placeholder).

What to implement here:
- Centralized logging configuration and helpers for structured logs
"""
import logging

logger = logging.getLogger("sim-tools")
logging.basicConfig(level=logging.INFO)

def get_logger():
    return logger
