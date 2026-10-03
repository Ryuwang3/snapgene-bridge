# Repository instructions

## Scope

This repository designs primers locally and uses a local SnapGene install,
reached through its official `--convert` command line on a "node" machine,
as the authority for binding sites and Tm. Do not add code injection, binary
patching, decompiled entry points, or GUI automation as a data source. The
only GUI-level code allowed is read-only dialog diagnosis after a timeout
(`node/backends.py`).

## Ground rules

1. Every CLI command prints one JSON object (see `docs/json-contract.md`).
   Expected failures raise a `BridgeError` subclass with a stable `code`.
2. Bridge-internal coordinates are zero-based and half-open; on circular
   molecules `end <= start` wraps through the origin. Command arguments use
   1-based inclusive `a..b` and are converted by `seqtools.parse_location`.
3. Every Tm in output carries `tm_standard`. Never label a local estimate as
   a SnapGene value.
4. Never overwrite an existing file unless the caller passes `--force`.
5. Node code (`node/`, `snapgene_genbank.py`, `protocol.py`, `models.py`,
   `errors.py`) must import only the standard library plus `sgffp`.
6. When SnapGene behaviour is relied on, record the verified version in the
   code comment and in `docs/research/snapgene-platform.md`.

## Before handing work back

- `uv run --group dev python -m pytest` (unit tests, no SnapGene needed).
- `uv run --group dev ruff check src tests` and `ruff format --check`.
- If node, protocol, or design code changed and a node is configured:
  `snapgene-bridge deploy`, then `uv run --group dev python -m pytest -m node`.

## Fixtures

`tests/data` and `src/snapgene_bridge/selftest_data` hold only synthetic
random sequences and the public pUC19 record. Never add laboratory plasmids.

## Documentation style

Write technical documentation in plain language. Avoid formulas in
parentheses; if a document needs a complex expression, put it on its own
display-math lines according to the workspace instructions.
