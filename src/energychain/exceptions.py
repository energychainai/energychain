"""Public framework error types."""

class EnergyChainError(Exception):
    """Base EnergyChain exception."""

class ValidationError(EnergyChainError, ValueError):
    """Invalid domain input or measurement."""

class AssetNotFound(EnergyChainError, LookupError):
    """Requested asset or site is missing."""

class PermissionDenied(EnergyChainError):
    """Principal is not authorized to access an energy resource."""

class ApprovalRequired(PermissionDenied):
    """An action requires an external approval."""

class UnsupportedCapability(EnergyChainError):
    """The connector does not support the requested capability."""

class StaleReading(EnergyChainError):
    """An observation is too old for the requested operation."""

class ToolError(EnergyChainError):
    """A tool failed during execution."""
