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
| Official CLI | Useful for fixed batch operations such as conversion and map export. | Treat it as an optional black-box helper, not an evaluator. |
| GUI automation | Can open files and demonstrate UI flows, but is fragile as a data interface. | Keep it optional and evidence-oriented. |
| File-first bridge | External engines can calculate primers and write a new artifact for review. | Use this as the MVP architecture. |

The phrase “black-box CLI” means that the process accepts a documented file and
arguments and returns a documented file or image. It does not mean that an
agent can send arbitrary commands into the running application.

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
