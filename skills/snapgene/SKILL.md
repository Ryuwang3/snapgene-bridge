# SnapGene Bridge skill

Use this skill when a user asks to inspect a SnapGene file, design primers, or
prepare a plasmid artifact for review.

## Operating procedure

1. Run `snapgene-bridge status` and inspect the reported capabilities.
2. Run `snapgene-bridge read INPUT` before designing anything. Confirm the
   molecule name, length, topology, features, and existing primers.
3. Keep coordinates zero-based and half-open when calling the CLI.
4. Run `snapgene-bridge primers INPUT --target START END` with a declared
   thermodynamic standard. The current supported standard is `primer3`.
5. If writing a result, choose a new output path. Do not overwrite the input
   unless the user explicitly requests `--force`.
6. Report the output path, pair index, Tm standard, and any warnings.
7. Run `snapgene-bridge validate OUTPUT`, then offer or run `snapgene-bridge
   open OUTPUT --dry-run` before using a desktop open command.

## Scientific boundaries

- Treat the program as the source of calculated sequence content and the
  language model as the planner and explainer.
- Never claim that a Primer3 Tm is identical to SnapGene or a vendor calculator.
- Do not infer a cloning result from a screenshot when the sequence file can be
  inspected directly.
- Do not patch, inject into, or reverse-engineer the SnapGene executable.
- Never upload private plasmids to a hosted service unless the user explicitly
  authorizes that route.

## Failure handling

The CLI returns JSON even on expected failures. Read `error.code`, show the
message and hint, and resolve missing optional dependencies before retrying.
Do not parse prose from stderr as a substitute for the JSON contract.
