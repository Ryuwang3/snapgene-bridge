"""Errors exposed by the bridge and converted to stable CLI JSON."""


class BridgeError(Exception):
    """Base class for expected, user-actionable failures."""

    code = "bridge_error"

    def __init__(self, message: str, *, hint: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.details = details or {}

    def as_dict(self) -> dict:
        result: dict = {"code": self.code, "message": self.message}
        if self.hint:
            result["hint"] = self.hint
        if self.details:
            result["details"] = self.details
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


class DesignError(BridgeError):
    """No candidate satisfied the design constraints."""

    code = "no_valid_design"


class NodeNotConfiguredError(BridgeError):
    code = "node_not_configured"


class NodeUnreachableError(BridgeError):
    code = "node_unreachable"


class NodeError(BridgeError):
    """The node answered with an error (deployment, SnapGene, or protocol)."""

    code = "node_error"


class SnapGeneBusyError(NodeError):
    code = "snapgene_busy"


class SnapGeneTimeoutError(NodeError):
    code = "snapgene_timeout"


class SnapGeneNotFoundError(NodeError):
    code = "snapgene_not_found"


def error_from_dict(data: dict) -> BridgeError:
    """Rebuild a typed error from a node response."""

    classes = {
        cls.code: cls
        for cls in (
            InputError,
            NodeError,
            SnapGeneBusyError,
            SnapGeneTimeoutError,
            SnapGeneNotFoundError,
            DependencyMissingError,
            OperationUnavailableError,
        )
    }
    cls = classes.get(data.get("code", ""), NodeError)
    return cls(
        data.get("message", "Node reported an error."),
        hint=data.get("hint"),
        details=data.get("details"),
    )
