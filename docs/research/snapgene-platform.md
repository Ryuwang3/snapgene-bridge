# SnapGene platform research note

This note preserves the evidence behind the initial repository boundary. It is
not a promise that vendor behavior will remain unchanged. Re-check the official
pages before publishing a release or making a legal claim.

## Findings from the initial discussion

The Claude Code session titled “SnapGene AI插件开发探讨” reviewed the
following routes:

| Route | Working conclusion | Repository implication |
| --- | --- | --- |
| Embedded plugin | No supported public plugin boundary was found in the reviewed material. | Do not build around an undocumented in-process API. |
| Official CLI | Conversion and map export only, but GenBank-SnapGene import computes primer sites and Tm. | Used as the Tm and binding-site oracle (ADR 0002). |
| GUI automation | Can open files and demonstrate UI flows, but is fragile as a data interface. | Keep it optional and evidence-oriented. |
| File-first bridge | External engines can calculate primers and write a new artifact for review. | Use this as the MVP architecture. |

The phrase “black-box CLI” means that the process accepts a documented file and
arguments and returns a documented file or image. It does not mean that an
agent can send arbitrary commands into the running application.

## Verified behaviour (SnapGene 8.0.0, Windows 11, 2026-10-03)

These observations come from running the official `SnapGene.exe` command line
through WSL interop. The regression data in `src/snapgene_bridge/selftest_data`
was recorded in the same session.

| Observation | Evidence |
|---|---|
| `--help` exits 0 but prints nothing on Windows | Output was empty with pipes and under a pseudo-terminal |
| `--convert` blocks on the first-run name/e-mail dialog until it is completed once in the GUI | UI Automation read the dialog: 名称, 电子邮件, 可以, 取消. Clicking Cancel quits without output. |
| `.dna` to `.dna` conversion is a byte-identical copy | Checked with `cmp` |
| The output extension is normalised: a `.gb` export target is written as `.gbk` | Observed |
| GenBank import creates primers only when the `JOURNAL   Exported ... from SnapGene ...` line is present | 5 variants: colour name language and label quoting had no effect |
| Imported primers get SnapGene-computed binding sites, integer Tm and alignment components | Re-import of SnapGene's own export reproduced the stored values |
| Location hints on `primer_bind` are ignored | 198 of 198 primers identical with true and with dummy hints |
| Primers without any site of Tm 40 C or more are not imported | 36 of 2000 random primers; all short and AT-rich |
| Batch cost is dominated by startup | 200 or 1000 primers in one file took 4.8 s; 20 files took 6.7 s |
| A 65 nt primer note on one long line imports correctly | `check` with a 45 nt tail |
| A textbook nearest-neighbour model matched SnapGene's integer Tm in 61 % of 2162 perfect-match sites, with a mean absolute error of 0.51 C | Basis for using SnapGene rather than re-implementing it |

## Candidate components

- [`sgffp`](https://github.com/merv1n34k/sgffp) provides a Python reader and
  writer for SnapGene sequence files. The repository is MIT licensed and should
  be pinned and regression-tested before a production release.
- [`primer3-py`](https://pypi.org/project/primer3-py/) provides the initial
  thermodynamic backend. Its values must be labeled `primer3` in output.
- [`pydna`](https://github.com/pydna-group/pydna) is the planned PCR and
  assembly simulation backend.
- [OpenCloning](https://github.com/OpenCloning/OpenCloning) is a useful
  reference for open cloning workflows, but it is not the bridge's file
  adapter.
- [CLI-Anything](https://github.com/HKUDS/CLI-Anything) motivates the
  command-plus-skill packaging pattern. Its harness-generation workflow cannot
  create an undocumented SnapGene API by itself.

## Official pages to re-check

- [Does SnapGene have an API?](https://support.snapgene.com/hc/en-us/articles/13602425878420-Does-SnapGene-have-an-API)
- [SnapGene Server Request API](https://support.snapgene.com/hc/en-us/articles/10387315758100-SnapGene-Server-Request-API)
- [Operations](https://support.snapgene.com/hc/en-us/articles/10387343966100-Operations)
- [Command Line: Converting File Formats](https://support.snapgene.com/hc/en-us/articles/10384393330836-Command-Line-Converting-File-Formats)
- [Command Line: Creating Maps of DNA Sequences](https://support.snapgene.com/hc/en-us/articles/10384408885268-Command-Line-Creating-Maps-of-DNA-Sequences)
- [What is Genbank - SnapGene Format?](https://support.snapgene.com/hc/en-us/articles/10242682237588-What-is-Genbank-SnapGene-Format)

## REA-verified CLI surface (SnapGene 8.0.0, Windows 11, 2026-10-18)

This section was produced on the same node with REA 6.5.0 and Ghidra 12.1.4 in
read-only mode. REA read the shipped `SnapGene.exe`; it did not inject into,
patch, or run SnapGene as a data source. The observations below are the
command-line surface only, and they reproduce and extend the 2026-10-03 entry.

Target identity:

- `C:\Program Files\SnapGene\SnapGene.exe`, 37,611,928 bytes.
- SHA-256 `86164d9da2ba268b1d467c9abcdf872159fb3edd72af96e85806ce2c0466f98f`.
- Version resource read independently: ProductVersion 8.0.0, FileVersion 8.0.0,
  CompanyName GSL Biotech LLC, OriginalFilename SnapGene.exe.
- REA analysis of that exact digest: format pe, architecture x86_64,
  image base 0x140000000, 9 segments, 79,464 procedures, 41,118 defined strings
  (Evidence `ev_687775b524400fbaedcd5d4c61206a1a0a255866b4d530f7e75f8ade089883f5`).

Command-line behaviour. Each case ran with its own redirected stdout and
stderr through `Start-Process -PassThru`, and its exit code was recorded:

| Invocation | Exit code | stdout | stderr | Outcome |
| --- | --- | --- | --- | --- |
| `--help` | 0 | 0 B | 0 B | returns at once, prints nothing |
| `--version` | 0 | 0 B | 0 B | returns at once, prints nothing |
| `--definitely-not-a-flag` | 0 | 0 B | 0 B | returns at once, prints nothing |
| no arguments | not observed | - | - | did not return; the live process had to be killed |

The table is the reason this note treats the CLI as un-introspectable:

- The three flag cases are indistinguishable from one another. An agent cannot
  tell a supported flag from an unknown one through the exit status or output,
  so the bridge must not treat exit 0 as proof that an option was understood.
- `--help` printing nothing is not a bug in the bridge's argument handling; it
  is the observed behaviour of the vendor binary.
- The no-argument case starts the GUI and blocks. That matches the repository's
  existing rule that the CLI cannot run while the GUI is open, and it is one
  more way a node can appear hung.

This does not establish which flags exist. It establishes that the binary will
not tell you, which is the fact the bridge's design already assumes: version
detection reads the PE version resource, and capability discovery does not
depend on CLI output.

## REA analysis boundary on this target

REA's Windows Ghidra lane completed a full auto-analysis of the 37.6 MB binary,
but not under the default budget. The observed startup outcomes were:

| Analyzer preset | Startup budget | Result |
| --- | --- | --- |
| `ghidra-default` | 330 s | `provider_timeout` |
| `ghidra-default` | 1,800 s | `provider_timeout` |
| `ghidra-default+disabled:WindowsResourceReference` | 5,400 s | overview returned in 2,337 s |

A 360,448-byte system executable (`notepad.exe`) completed the same
`binary_overview` operation in 231 s under `ghidra-default`, so the boundary is
target size, not the Windows lane.

Cold-session string searches are the practical limit for this target. On the
completed session, the first `search_strings` request had not returned after
29 minutes, and three further searches on the same target did not return within
a further 15 minutes. Those are upper bounds from requests that were stopped,
not completed measurements. A snapshot saved from a successful `analyze`
(14,958 bytes) did not remove that cost: a `search_strings` request against
the saved snapshot was still running after about 20 minutes and was stopped.

Consequence for this repository: REA is usable here for artifact identity and
structure, and it is not yet a practical way to enumerate SnapGene's internal
strings on this host. Anything that depends on internal symbols has to come from
the CLI behaviour rather than from static symbol recovery.

## Re-check the boundary before relying on this note

These are single-host observations from 2026-10-18, not guarantees. Before
publishing a release or making a legal claim, re-run the command-line probe and
re-read the target digest. The REA side of the note depends on Ghidra 12.1.4,
JDK 21 and `REA_GHIDRA_DISABLED_ANALYZERS=WindowsResourceReference`; a different
preset or a newer Ghidra can change both the timing and whether analysis
completes at all.

## Open questions before a public release

1. Which SnapGene or Viewer versions are used in the lab?
2. Can the lab provide synthetic or de-identified `.dna` fixtures for round
   trips?
3. Which cloning methods and polymerase profiles are required first?
4. Which order-sheet vendor schema should be supported?
5. Does the lab have a license or institutional access to any official server
   integration that changes the supported boundary?
