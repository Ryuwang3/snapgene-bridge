# SnapGene Bridge

SnapGene Bridge is a local, agent-native workflow for molecular biology work
around SnapGene-compatible files. It lets an agent inspect a molecule, design
primers with a declared thermodynamic standard, validate the result, and write
a new annotated file for human review in SnapGene.

This project is deliberately **file-first**. It is not an embedded SnapGene
plugin and it does not patch, inject into, or modify the SnapGene executable.
The public integration boundary is the sequence file plus an explicit JSON
command contract.

## Why this shape

Virtuoso Bridge can evaluate code inside Virtuoso because Cadence exposes an
in-process SKILL interpreter and IPC hooks. SnapGene's public command-line
surface is a batch interface for fixed operations such as format conversion
and map export. It does not expose an equivalent arbitrary evaluation endpoint
for a running document. GUI automation can be added later for convenience,
but it is not a reliable source of sequence state.

The bridge therefore keeps the scientific work deterministic and local:

```text
agent request
    -> JSON CLI
    -> normalized molecule model
    -> primer3 / cloning engines
    -> validation and audit record
    -> new .dna or GenBank file
    -> SnapGene for human review
```

The agent chooses a strategy and explains it. The program computes sequences,
coordinates, thermodynamic values, and file changes. An output is never
written over an input unless the caller explicitly passes `--force`.

## Quick start

The base package reads FASTA files without optional dependencies:

```bash
uv sync
uv run snapgene-bridge status
uv run snapgene-bridge read examples/mini-plasmid.fasta
```

Enable the adapters used by the full workflow:

```bash
uv sync --extra full
uv run snapgene-bridge status
uv run snapgene-bridge read plasmid.dna
uv run snapgene-bridge primers plasmid.dna --target 120 840 --output output/plasmid-with-primers.dna
uv run snapgene-bridge open output/plasmid-with-primers.dna --dry-run
```

Every command emits a JSON object. Coordinates in the bridge contract are
zero-based and half-open. Primer results include `tm_standard` and currently
use `primer3`; they are not presented as SnapGene or NEB calculator values.

## Repository map

- `src/snapgene_bridge/` contains the normalized data model, format adapters,
  Primer3 operation, and JSON CLI.
- `skills/snapgene/SKILL.md` gives Claude Code an agent-facing operating
  procedure.
- `docs/research/` records the platform investigation behind the integration
  boundary.
- `docs/decisions/` records architectural choices that should not be silently
  reversed.
- `docs/json-contract.md` defines the machine-readable command envelope.
- `docs/roadmap.md` separates the runnable MVP from later cloning and desktop
  conveniences.

## Current boundary

Implemented in the MVP:

- FASTA read and write.
- Optional GenBank read and write through Biopython.
- Optional `.dna` read and write through `sgffp`.
- Optional PCR primer design through `primer3-py`.
- Stable JSON envelopes for `status`, `read`, `validate`, `primers`, and
  `open`.
- Explicit capability reporting when optional libraries or the desktop app are
  unavailable.

Planned after real test files are available:

- PCR and Gibson or HiFi simulation through `pydna`.
- Double-stranded off-target scans and sequencing-primer design.
- Construction-history export and regression fixtures from real SnapGene files.
- A platform-specific GUI adapter that only opens and verifies generated files.

The first real acceptance fixture should be a synthetic or non-sensitive
plasmid supplied by the user. Private laboratory files must stay out of Git.

## Research basis

The initial design was distilled from the Claude Code discussion titled
“SnapGene AI插件开发探讨” on 2026-10-02 and 2026-10-03. The source links and
the claims that still need re-verification before a public release are listed
in [the research note](docs/research/snapgene-platform.md).
