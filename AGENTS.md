# Repository instructions

## Scope

This repository implements a local, file-first bridge for SnapGene-compatible
sequence workflows. Keep SnapGene itself outside the trusted execution
surface. Do not add code injection, binary patching, undocumented RPC calls,
or reverse-engineered executable entry points.

## Development workflow

1. Keep all agent-facing commands deterministic and JSON serializable.
2. Use zero-based, half-open coordinates at the bridge boundary.
3. Never overwrite a sequence file by default. Require a new output path or
   an explicit `--force`.
4. Import optional scientific libraries lazily and return a clear dependency
   error with an install hint.
5. Record the thermodynamic standard beside every reported melting temperature.
6. Add synthetic fixtures and a focused test when changing an adapter or the
   JSON contract.
7. Run `python -m pytest` before handing work back.

## Documentation style

Write technical documentation in plain language. Avoid embedding formulas in
parentheses. If a future document needs a complex mathematical expression,
put it on its own display-math lines according to the workspace instructions.
