# Changelog

## 0.2.0 (2026-10-03)

- SnapGene's official `--convert` command line is now the source of every
  reported Tm and binding site (ADR 0002). Values are labelled
  `snapgene-<version>`; offline estimates are labelled `estimate:nn`.
- New commands: `init`, `deploy`, `status` (with node health), `selftest`,
  `check`, `pcr`, `clone`. The old `primers` command is removed.
- Node side (`python -m snapgene_bridge.node`) with WSL/Windows backend,
  batch conversion, timeout handling with dialog diagnosis, and locking.
- GenBank output now uses the GenBank-SnapGene flavour, so SnapGene imports
  the primers instead of plain features.
- Fixed `.dna` reading of origin-spanning features on circular plasmids,
  which previously failed validation.
- `.dna` output no longer stores binding sites with a non-SnapGene Tm.
- JSON schema version 2; Python 3.11 or newer.

## 0.1.0

- File-first bridge boundary, JSON CLI envelope, FASTA/GenBank/`.dna`
  adapters, Primer3 design.
