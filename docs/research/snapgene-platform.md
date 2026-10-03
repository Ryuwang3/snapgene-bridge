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

## Open questions before a public release

1. Which SnapGene or Viewer versions are used in the lab?
2. Can the lab provide synthetic or de-identified `.dna` fixtures for round
   trips?
3. Which cloning methods and polymerase profiles are required first?
4. Which order-sheet vendor schema should be supported?
5. Does the lab have a license or institutional access to any official server
   integration that changes the supported boundary?
