# Initial design discussion distilled

The source discussion started from a request to make SnapGene feel like an
AI-native application for primer design and plasmid work. The useful parts of
the discussion reduce to five product principles:

1. Keep unpublished sequences local.
2. Let the program, rather than the language model, compute every base,
   coordinate, and melting temperature.
3. Simulate and validate a proposed construct before writing it.
4. Preserve the user's SnapGene-centered review workflow by emitting a native
   or importable sequence artifact.
5. Expose the workflow as CLI plus JSON plus agent skill so it can be called by
   Claude Code or a future MCP client.

The discussion also identified a real usability issue: Primer3, SnapGene, and
vendor calculators can report different Tm values for the same oligo. The
repository therefore records the calculation standard beside every Tm instead
of pretending that the values are interchangeable.

The first end-to-end acceptance test should be:

1. Read a non-sensitive plasmid file.
2. Select a target interval.
3. Design a PCR primer pair with the declared standard.
4. Check the pair's coordinates and product range.
5. Write a new file containing the primers.
6. Open the new file in SnapGene for human inspection.
