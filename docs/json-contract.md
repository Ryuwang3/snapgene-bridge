# JSON contract (schema 2)

Every command writes one JSON object to standard output:

```json
{"schema_version": "2", "ok": true, "command": "clone", "...": "..."}
```

Expected failures:

```json
{
  "schema_version": "2",
  "ok": false,
  "command": "clone",
  "error": {"code": "snapgene_busy", "message": "...", "hint": "...", "details": {}}
}
```

Exit status:

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected internal error |
| 2 | Expected user, dependency, or node error |
| 3 | `selftest` ran but found mismatches |

## Conventions

- `start`/`end`: zero-based, half-open, top strand. On circular molecules
  `end <= start` wraps through the origin.
- `location`: the same interval as SnapGene shows it, 1-based inclusive
  `a..b`. Command arguments use this form.
- `strand` of a primer site: `+` when the primer sequence equals the top
  strand, `-` when it equals the bottom strand.
- `tm_standard`:

  | Value | Meaning |
  |---|---|
  | `snapgene-<version>` | Computed by SnapGene |
  | `estimate:nn` | Local nearest-neighbour estimate |
  | `snapgene-file` | Value stored in an input `.dna`, computed by whichever SnapGene saved it |
  | `unknown` | Source not known |

## Site object

```json
{
  "start": 2460, "end": 2486, "location": "2461..2486", "strand": "-",
  "tm": 60.0, "annealed_length": 26, "annealed": "ATGAGT...",
  "components": [{"bases": "GCGCTAGC"}, {"bases": "ATGAGT...", "hybridized": [2460, 2486]}]
}
```

Each entry in `components` describes part of the primer:

- With `hybridized`: those bases pair with that template interval.
- Without it: those bases do not pair (5' tail, mismatch). A template base
  missing between two hybridized parts is a bulge.

## Commands

| Command | Main fields |
|---|---|
| `init` | `config`, `next_steps` |
| `status` | `local_dependencies`, `config`, `node` (node status plus `problems`), `ready` |
| `deploy` | `wheel`, `client_version`, `node` (node status after install) |
| `selftest` | `passed`, `suites[]` with `mismatches` |
| `read` | `record`: normalized molecule with features and primers |
| `validate` | `length`, `topology`, `features[]` with `location` |
| `check` | `tm_standard`, `oracle`, `primers[]` (`imported`, `sites[]`), optional `output` |
| `pcr`, `clone` | See below |

`pcr` and `clone` return a `design` object with these fields:

- `tm_standard` and `oracle`: source, SnapGene version, and elapsed time.
- `region`.
- `settings`.
- `best` and `alternatives[]`. Each pair has:
  - `forward` and `reverse`: `sequence`, `tail`, `anneal`, `tm`,
    `estimated_tm`, `site`, `off_targets[]`;
  - `tm_difference`;
  - `product`: `location`, `length`, `sequence`;
  - `checks`: primer3 hairpin and dimer values plus `warnings`.
- `candidates`: counts evaluated, usable, and rejected by reason.
- `warnings`.

The command result may also contain `output`, `order_sheet`, and top-level
`warnings`; offline runs always add one.
