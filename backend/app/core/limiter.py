"""SlowAPI rate limiter instance and configuration."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter keyed by client remote IP address
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
