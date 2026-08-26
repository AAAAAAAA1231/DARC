"""A-share quantitative signal and risk-control assistant.

This package produces probability-weighted signals, adaptive stops, and
risk-limited position suggestions. It does not claim to forecast every
stock, and it is not a live broker.
"""

from .config import AppConfig, load_config

__version__ = "0.1.0"
__all__ = ["AppConfig", "load_config", "__version__"]
