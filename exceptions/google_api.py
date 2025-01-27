class CredentialsNotAvailableError(Exception):
    """Exception raised when credentials are not available for an operation."""

    def __init__(self, message="Required credentials are not available."):
        super().__init__(message)
