# JSON contract

Every command writes one JSON object to standard output. The top-level shape is

```json
{
  "schema_version": "1",
  "ok": true,
  "command": "read"
}
```

Successful commands add command-specific fields. Expected failures use

```json
{
  "schema_version": "1",
  "ok": false,
  "command": "read",
  "error": {
    "code": "dependency_missing",
    "message": "...",
    "hint": "..."
  }
}
```

The process exit status is zero for success, two for an expected user or
dependency error, and one for an unexpected internal error.

## Molecule record

`read` returns a normalized record with these fields:

- `name`: source record name.
- `sequence`: uppercase IUPAC DNA sequence.
- `length`: sequence length.
- `topology`: `linear` or `circular`.
- `features`: annotated intervals.
- `primers`: primer definitions and optional binding intervals.
- `source_format`: adapter name.
- `metadata`: adapter-specific information.

Feature and primer binding coordinates are zero-based and half-open. A Primer3
result additionally includes `tm_standard`, which is `primer3` in the current
release.
