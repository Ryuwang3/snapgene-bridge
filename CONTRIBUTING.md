# Contributing

The project is in an alpha research stage. Keep changes small and make every
new operation deterministic, inspectable, and safe to run against a copy of a
sequence file.

Before opening a change:

1. Run `python -m pytest`.
2. Run `python -m ruff check .` when Ruff is available.
3. Check that CLI failures remain JSON objects with a stable `error.code`.
4. Add a decision record when a new external integration changes the trust
   boundary or file-writing behavior.

Do not commit private plasmid files, sequencing traces, API keys, or generated
`.dna` outputs. Use small synthetic sequences in tests.
