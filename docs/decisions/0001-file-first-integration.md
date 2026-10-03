# ADR 0001: File-first integration boundary

## Status

Accepted for the MVP.

## Context

The desired user experience resembles an agent-native bridge: the agent should
understand a cloning request, calculate primers, and leave a reviewable design
in a familiar molecular-biology application. Virtuoso Bridge achieves a
similar experience by using an official in-process interpreter and IPC
mechanism. The public SnapGene material reviewed in the initial discussion did
not expose an equivalent arbitrary evaluation endpoint for a running document.

## Options considered

1. **Embedded plugin or in-process bridge.** This would give the most direct
   control, but there is no supported public plugin boundary to target.
2. **Black-box command-line wrapper.** This is dependable for fixed batch
   operations, but it does not mean arbitrary control of a running GUI.
3. **GUI automation as the primary interface.** This can demonstrate menu
   flows, but it is fragile and does not expose all sequence state.
4. **External scientific engine plus file output.** This keeps calculations
   testable and produces a native artifact for human review.

## Decision

Use option 4 as the core. Add documented command-line operations and optional
desktop conveniences around it. The bridge writes new files and never relies
on undocumented executable interfaces.

## Consequences

Positive:

- Scientific operations can run locally and be regression tested.
- The agent receives structured data rather than screenshots alone.
- Users keep SnapGene as the review and editing surface.
- The design can support multiple file formats and future MCP clients.

Trade-offs:

- The bridge does not mutate a document already open in SnapGene.
- Primer and assembly calculations may differ from SnapGene's private
  algorithms; the selected standard must be shown to the user.
- The `.dna` adapter depends on a community-maintained parser and needs
  fixtures for each SnapGene format revision used by the lab.
