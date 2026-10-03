# Architecture

## Trust boundary

The bridge trusts only local input files, the explicitly selected scientific
libraries, and the command arguments supplied by the user or agent. SnapGene
is a viewer and review surface. A generated file is opened there after the
bridge has completed validation.

The bridge does not assume that a file open in SnapGene will reload after an
external write. Operations therefore write a new path and ask the user to
review that path.

## Layers

### Command layer

`cli.py` exposes a small command set and one JSON envelope. An error has a
stable `error.code`, a human-readable message, and an optional install or
recovery hint. This makes the CLI usable by Claude Code, shell scripts, and a
future MCP wrapper without scraping human-oriented text.

### Model layer

`models.py` converts format-specific coordinates into one contract. Features
and primer binding sites use zero-based, half-open intervals. Validation is
performed before a file is written.

### Adapter layer

- FASTA is implemented with the Python standard library.
- GenBank is loaded lazily through Biopython.
- SnapGene files are loaded lazily through `sgffp`.

An adapter may preserve more metadata than the normalized model, but it must
not change the coordinate contract.

### Operation layer

`primer_design.py` calls Primer3 through `primer3-py`. It records the selected
standard in every primer. A later polymerase-specific backend must publish a
separate name and calibration evidence rather than silently replacing the
Primer3 values.

## Future adapters

The desktop adapter may provide `open`, application detection, and screenshot
evidence. It must remain optional and must never be treated as the source of
truth for sequence content. A future MCP server can call the same Python
operations and expose the same JSON objects.
