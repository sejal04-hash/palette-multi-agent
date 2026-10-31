class PaletteError(Exception):
    """Base exception for Palette."""
    pass


class APIKeyError(PaletteError):
    """Raised when an API key is missing or invalid."""
    pass


class ProviderError(PaletteError):
    """Raised when a model provider fails."""
    pass


class QuotaError(PaletteError):
    """Raised when provider credits/quota are exhausted."""
    pass


class ModelNotFoundError(PaletteError):
    """Raised when the requested model is unavailable."""
    pass