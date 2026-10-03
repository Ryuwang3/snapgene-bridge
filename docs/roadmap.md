# Roadmap

## Done in 0.2.0

- [x] SnapGene command line as the Tm and binding-site oracle (ADR 0002).
- [x] SSH node transport, `init`, `deploy`, `status`.
- [x] `selftest` pinned to SnapGene 8.0.0 output for 208 primers.
- [x] `check`: SnapGene sites, Tm, alignment components, off-targets.
- [x] `clone`: fixed-end cloning primers with 5' tails, chosen by SnapGene Tm.
- [x] `pcr`: flanking primers proposed by primer3 and re-ranked by SnapGene.
- [x] SnapGene-generated `.dna` output and tab-separated order sheets.
- [x] Circular templates, including regions and products across the origin.

## Next

- [ ] Gibson/HiFi and In-Fusion: overlap design with overlap Tm checked
  through the same oracle, plus product verification.
- [ ] Sequencing primers: tiling a construct with SnapGene-verified sites.
- [ ] Site-directed mutagenesis primers.
- [ ] Reuse of the lab's existing primers before designing new ones.
- [ ] Vendor-specific order sheets: configurable columns, scale and
  purification.
- [ ] Carry feature colours and notes into `--output` by editing the input
  `.dna` instead of regenerating it.
- [ ] MCP server over the same operations.
- [ ] Verify the macOS and Linux node backends on real installs.

## Not planned

- Injecting into or patching SnapGene, or calling undocumented internals.
- GUI automation as a data source.
- Re-implementing SnapGene's hybridization algorithm.
