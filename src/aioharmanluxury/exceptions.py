"""Exceptions for aioharmanluxury."""


class HarmanLuxuryError(Exception):
    """Base error for all Harman Luxury failures."""


class HarmanLuxuryConnectionError(HarmanLuxuryError):
    """Raised when the device cannot be reached."""
