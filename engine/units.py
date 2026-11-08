"""
Central UnitRegistry configuration for Aavaran using Pint.

Defines standard dimensional units for packaging permeance, transmission rates,
and food physical metrics:
- OTR: cc / (m² · day · atm)
- WVTR: g / (m² · day)
- Permeance: g / (m² · day · kPa)
"""

import pint

ureg = pint.UnitRegistry()
# Define alias cc if not present
try:
    ureg.define("cc = cubic_centimeter")
except Exception:
    pass

Q_ = ureg.Quantity

__all__ = ["ureg", "Q_"]
