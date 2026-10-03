# Security and data handling

The bridge is built for unpublished sequences:

- Sequences leave this machine only over SSH, to the SnapGene node configured
  in `~/.config/snapgene-bridge/config.toml`. Nothing is sent to third-party
  services.
- The node writes temporary files under its scratch directory and deletes
  them after each run. `keep_files` is a debugging option.
- On the node, the bridge starts only `SnapGene --convert`. It refuses to run
  while SnapGene is open. After a timeout it stops only the SnapGene
  processes that appeared during that run. It does not change system or
  SnapGene settings.

When reporting a bug, replace private sequences with a small synthetic
fixture. Do not attach `.dna` files from the lab, sequencing traces,
credentials, or order sheets.

Report a suspected vulnerability privately to the maintainers before opening
a public issue.
