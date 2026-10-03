# Roadmap

## M0: repository and contract

- [x] Create the normalized molecule model.
- [x] Add JSON CLI envelopes and capability reporting.
- [x] Add safe, non-overwriting file output.
- [x] Add Claude Code skill instructions.

## M1: first scientific workflow

- [x] Read and write FASTA.
- [x] Optional `.dna` read and write through `sgffp`.
- [x] Optional GenBank conversion through Biopython.
- [x] Primer3 PCR primer design with explicit Tm standard.
- [ ] Add a synthetic `.dna` round-trip fixture.
- [ ] Add full-length product validation after in-silico PCR.

## M2: cloning operations

- [ ] Add pydna-backed PCR simulation.
- [ ] Add Gibson or HiFi assembly planning.
- [ ] Add Golden Gate and restriction-cloning planning.
- [ ] Serialize construction history when the input and output format support
  it.
- [ ] Add sequencing-primer coverage checks.

## M3: laboratory integration

- [ ] Add a local inventory index for approved plasmids and reusable primers.
- [ ] Add organization-specific polymerase profiles with documented Tm rules.
- [ ] Add order-sheet exporters with a configurable vendor schema.
- [ ] Add an MCP facade over the same CLI operations.

## M4: desktop convenience

- [ ] Detect SnapGene and SnapGene Viewer installations.
- [ ] Open generated files and collect a user-visible screenshot.
- [ ] Add accessibility-only helpers for menu navigation where testing shows
  they are stable.

Desktop automation remains a convenience layer. It does not become an
in-process SnapGene API.
