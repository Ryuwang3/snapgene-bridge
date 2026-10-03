# Examples

All examples use the public pUC19 record shipped as a test fixture
(`tests/data/pUC19_L09137.gb`, GenBank L09137, circular, 2686 bp). Its AmpR
(bla) coding sequence is `complement(1626..2486)`.

Check two primers against SnapGene:

```bash
sgb check tests/data/pUC19_L09137.gb --primer M13F=GTAAAACGACGGCCAGT --primer bla_F=ATGAGTATTCAACATTTCCGTGTCGC
```

Subclone AmpR with NheI / XhoI tails:

```bash
sgb clone tests/data/pUC19_L09137.gb --region 1626..2486 --strand - --tail-f GCGCTAGC --tail-r GCCTCGAG --name bla --output output/bla.dna --order output/bla_order.tsv
```

Expected with SnapGene 8.0.0:

| Primer | Sequence | SnapGene Tm |
|---|---|---|
| bla_F26 | `GCGCTAGCATGAGTATTCAACATTTCCGTGTCGC` | 60 |
| bla_R24 | `GCCTCGAGTTACCAATGCTTAATCAGTGAGGC` | 60 |

SnapGene reports 26 annealed bases for bla_R24, because two tail bases pair
with the template by chance.

Amplify the whole AmpR region for screening PCR:

```bash
sgb pcr tests/data/pUC19_L09137.gb --target 1626..2486 --name AmpR
```

Run without a node (local estimates, labelled `estimate:nn`):

```bash
sgb clone tests/data/pUC19_L09137.gb --region 1626..2486 --strand - --offline
```
