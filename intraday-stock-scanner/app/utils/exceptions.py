class ScannerError(Exception):
    """Base scanner exception."""


class ProviderError(ScannerError):
    """Provider layer exception."""


class DataIntegrityError(ScannerError):
    """Raised when required data is missing."""
