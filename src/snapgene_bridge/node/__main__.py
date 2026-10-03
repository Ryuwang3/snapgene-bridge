"""Node entry point: read one JSON request on stdin, print one framed JSON response."""

from __future__ import annotations

import json
import sys
from typing import Any

from .. import __version__
from ..errors import BridgeError, InputError
from ..protocol import frame


def handle(request: dict[str, Any]) -> dict[str, Any]:
    from . import runner

    op = request.get("op")
    try:
        if op == "ping":
            return {"ok": True, "node_version": __version__}
        if op == "status":
            return runner.status(request)
        if op == "evaluate":
            return runner.evaluate(request)
        raise InputError(f"Unknown node operation {op!r}.")
    except BridgeError as error:
        return {"ok": False, "node_version": __version__, "error": error.as_dict()}
    except Exception as error:  # keep the wire contract for unexpected bugs
        return {
            "ok": False,
            "node_version": __version__,
            "error": {"code": "node_internal_error", "message": f"{type(error).__name__}: {error}"},
        }


def main() -> int:
    raw = sys.stdin.read()
    try:
        request = json.loads(raw)
    except ValueError as error:
        response = {
            "ok": False,
            "error": {"code": "bad_request", "message": f"Request is not JSON: {error}"},
        }
    else:
        response = handle(request)
    sys.stdout.write(frame(response))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
