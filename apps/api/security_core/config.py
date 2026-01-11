"""Security Core configuration (dormant, not used in runtime)."""
import os

# Main feature flag (dormant)
SECURITY_CORE_ENABLED = os.getenv("SECURITY_CORE_ENABLED", "false").lower() == "true"

# Control model flag (for service.py control check path)
CONTROL_MODEL_ENABLED = os.getenv("CONTROL_MODEL_ENABLED", "false").lower() == "true"

# Privacy Shield settings
privacy_max_chars = int(os.getenv("PRIVACY_MAX_CHARS", "50000"))

# Privacy Guard settings
source_safety_mode = os.getenv("SOURCE_SAFETY_MODE", "true").lower() == "true"
debug = os.getenv("DEBUG", "false").lower() == "true"

