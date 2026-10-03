"""Wire format between the client and a SnapGene node.

Requests are one JSON object on the node's standard input.  The response is
one JSON object framed by marker lines, so login banners, shell prompts, or a
trailing ``logout`` printed by the remote shell never corrupt it.
"""

from __future__ import annotations

import json
from typing import Any

PROTOCOL_VERSION = 1
BEGIN = "<<<SNAPGENE-BRIDGE:BEGIN>>>"
END = "<<<SNAPGENE-BRIDGE:END>>>"


def frame(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.setdefault("protocol", PROTOCOL_VERSION)
    return f"{BEGIN}\n{json.dumps(body, ensure_ascii=False)}\n{END}\n"


def unframe(text: str) -> dict[str, Any] | None:
    """Return the last framed JSON object in ``text``, or ``None``."""

    end = text.rfind(END)
    if end < 0:
        return None
    begin = text.rfind(BEGIN, 0, end)
    if begin < 0:
        return None
    return json.loads(text[begin + len(BEGIN) : end].strip())
