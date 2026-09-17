"""Vendedor Adaptável: local, stateful and policy-controlled sales runtime."""

__version__ = "0.1.0"

from .conversation import SellerEngine
from .storage import StateStore

__all__ = ["SellerEngine", "StateStore", "__version__"]
