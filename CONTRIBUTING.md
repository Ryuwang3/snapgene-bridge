# Contributing

Keep changes small. Every operation must stay deterministic, print one JSON
object, and never overwrite a sequence file without `--force`.

Before opening a change:

1. Run `uv run --group dev python -m pytest`.
2. Run `uv run --group dev ruff check src tests` and `uv run --group dev ruff format --check src tests`.
3. If you touched `node/`, `protocol.py`, `transport.py`, `snapgene_genbank.py`, or `design/`
   and have a node, run `snapgene-bridge deploy` and then `uv run --group dev python -m pytest -m node`.
4. Add a decision record when an integration changes the trust boundary or
   file-writing behaviour, and record any newly relied-on SnapGene behaviour
   with its version in `docs/research/snapgene-platform.md`.

Do not commit laboratory plasmids, sequencing traces, credentials, or order
sheets. Fixtures must be synthetic or public (see `tests/data`).
