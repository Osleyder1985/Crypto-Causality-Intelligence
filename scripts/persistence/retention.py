"""Retention operations exposed as an explicit, auditable maintenance task."""
from .market_writer import purge_expired_market_data

__all__ = ["purge_expired_market_data"]
