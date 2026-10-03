# ADR 0002: SnapGene's command line as the Tm and binding-site oracle

## Status

Accepted. Supersedes the "SnapGene is only a viewer" part of ADR 0001.

## Context

ADR 0001 kept every calculation outside SnapGene and labelled Primer3 values
as such. In practice users compare every number with what SnapGene shows, so
a different Tm standard reads as an error. On 2026-10-03 we verified on
SnapGene 8.0.0 (Windows 11, driven from WSL2):

- `SnapGene --convert "SnapGene DNA"` turns a GenBank file into `.dna`. When
  the GenBank carries SnapGene's own `JOURNAL   Exported ... from SnapGene`
  reference line, `primer_bind` features with a `sequence:` note become
  primers. SnapGene then computes their binding sites, Tm, and alignment
  components during import.
- Without that line the same features import as plain annotations.
- Converting `.dna` to `.dna` is a byte copy and computes nothing.
- One process converts a list of files (`--input-list`/`--output-list`); 1000
  primers took about 4.8 s, almost all of it startup.
- Location hints are ignored: 198 of 198 primers gave identical results with
  correct and with dummy hints.
- Results are deterministic and match the GUI (integer Tm).
- The command line blocks on any modal dialog and must not run while the GUI
  is open.

## Decision

- SnapGene, through its official command line only, is the source of every
  Tm and binding site the bridge reports as final.
- Local code proposes candidates (primer3 and a nearest-neighbour estimate)
  and selects among SnapGene's verdicts.
- SnapGene runs on a node reached over SSH. Requests are scripts on standard
  input, because Windows OpenSSH with a WSL shell drops command arguments.
- An offline estimate mode remains for development, and its values are
  labelled `estimate:nn`.

## Consequences

- Users see the same numbers in the bridge output and in SnapGene.
- The bridge depends on an observed behaviour (the `JOURNAL` trigger), not a
  documented API. `selftest` pins 208 primers to SnapGene 8.0.0 output so any
  change is detected immediately.
- Design runs need a node with the GUI closed; one run takes seconds.
- Re-implementing SnapGene's algorithm is out of scope. A textbook
  nearest-neighbour model matched only 61 % of SnapGene's integers, and
  SnapGene's dynamic-programming search also reports bulged and mismatched
  sites.
