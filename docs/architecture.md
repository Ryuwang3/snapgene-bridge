# Architecture

```text
client (agent machine)                         node (machine with SnapGene)
----------------------                         ----------------------------
cli.py         commands, JSON envelope
design/        candidates, screening, pairing
oracle.py      SnapGeneOracle | EstimateOracle
transport.py   SSH, script on stdin  ───────►  python -m snapgene_bridge.node
                                                node/runner.py   batch job runner
                                                snapgene_genbank.py  GenBank-SnapGene writer
                                                node/backends.py SnapGene.exe via WSL interop
                                                  └─ SnapGene --convert (one process per batch)
                                                sgffp            read binding sites back
```

## Request path

1. A design command builds candidates.
   - `clone`: every annealing length at both fixed insert ends.
   - `pcr`: unique primers from primer3 pairs, using SnapGene-like salt
     settings.
2. `SnapGeneOracle.evaluate` sends one job (template, primers, and optionally
   features) to the node.
3. The node takes a lock, refuses to run if SnapGene is already open, and
   writes GenBank-SnapGene files. It then runs `SnapGene --convert` on the
   whole list and parses each `.dna` with `sgffp`. The response is framed by
   marker lines, so shell noise cannot corrupt it.
4. The client matches each candidate to its intended site by strand and 3'
   end. The 5' edge may differ, because SnapGene extends the annealed region
   into tail bases that happen to pair. All other sites are off-targets.
5. Screening rejects candidates in three cases:
   - not imported, meaning SnapGene found no site with a Tm of at least 40 C;
   - intended site missing;
   - off-target at or above `offtarget_max_tm`.
6. Pairs are ranked by distance from the target Tm, then Tm difference, then
   length and 3' clamp. For PCR, primer3's own penalty is also used.
7. With `--output x.dna`, a second job containing the chosen primers is
   returned as SnapGene-generated `.dna` bytes.

## Failure handling

| Situation | Behaviour |
|---|---|
| GUI open on the node | `snapgene_busy`, nothing is started |
| Hidden dialog | `snapgene_timeout` after `timeout_s`, with the dialog text read through UI Automation. Only SnapGene processes that appeared during the run are stopped. |
| Node not installed | Framed `node_not_deployed` answer from the shell script; `deploy` fixes it |
| Version skew | `status` reports it; `deploy` fixes it |

## Data

- `selftest_data/` holds SnapGene 8.0.0 results for 208 primers: synthetic
  templates plus public pUC19.
- `tests/data/regression6.snapgene-8.0.0.dna` is a real SnapGene output used
  to test parsing without a node.
