"""Errors exposed by the bridge and converted to stable CLI JSON."""


class BridgeError(Exception):
    """Base class for expected, user-actionable failures."""

    code = "bridge_error"

    def __init__(self, message: str, *, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def as_dict(self) -> dict[str, str]:
        result = {"code": self.code, "message": self.message}
        if self.hint:
            result["hint"] = self.hint
        return result


class InputError(BridgeError):
    code = "invalid_input"


class ValidationError(BridgeError):
    code = "validation_error"


class DependencyMissingError(BridgeError):
    code = "dependency_missing"


class UnsupportedFormatError(BridgeError):
    code = "unsupported_format"


class OperationUnavailableError(BridgeError):
    code = "operation_unavailable"
