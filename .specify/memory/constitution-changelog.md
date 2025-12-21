# Constitution Changelog

## v2.0 (2025-12-21) - MAJOR

**Version Change:** v1.0 → v2.0 (MAJOR)

### Rationale for Major Bump

- Fundamental governance model change: phase-specific rules → conditional principles
- All Articles rewritten to be lifecycle-immutable
- Removed Article VII (Deferred Decisions) - removed entirely (no deferred decisions in constitution)
- Removed Article VIII (Roadmap Alignment) - phases are implementation concerns, not constitutional
- Removed Appendix B (Phase Mapping) - no longer applicable

### Modified Principles

- Article I.B: "Orchestration Framework: Phase 1–2 Baseline" → "Orchestration Framework: Pattern-Driven Selection"
- Article I.D: "Memory Layer: PostgreSQL-First (Phase 1–2)" → "Memory Layer: PostgreSQL-First Architecture"
- Article I.F: "UI Layer" - removed phase-specific references (e.g., "React Flow Phase 2")
- Article I.G: "Primary LLM Provider (Phase 1)" → "Primary LLM Provider"
- Article I.H: Removed phase references (e.g., "Fallback to Windmill; single-node Phase 1")
- Article II.A: Removed "Phase 1 Vertical Slice" concrete example; replaced with pattern
- Article II.B: Removed phase markers from Decision Pattern table
- Article II.C: "Phase 1 Baseline" confidence thresholds → "Baseline Configuration"
- Article II.E: "Multi-Storage Memory (Phase 3 Foundation)" → "Multi-Storage Memory Abstraction"
- Article II.F: Removed (Isolation Progression was phase-specific implementation detail)
- Article II.G: "Tool Gap Detection & Self-Extension (Phase 4+)" → "Tool Gap Detection & Self-Extension"
- Article III.F: Security section - removed phase progression; replaced with maturity triggers
- Article IV: "Failure Mode Detection & Recovery (Phase 2+)" → "Failure Mode Detection & Recovery"
- Article V.C: Removed "Ratification Schedule" (phase-bound)

### Removed Sections

- Article VII: Deferred Decisions (Phase 2+) - removed entirely (constitutions define what IS decided, not what might be)
- Article VIII: Alignment with Roadmap - phases are not constitutional concerns
- Appendix B: Quick Reference – Article to Phase Mapping
- Appendix C: Maturity-Triggered Expansions - removed (still deferred decisions in disguise)
- Appendix B (Technology Rationale Summary) - removed excessive justification content

### Added Sections

- Article II.F: Isolation & Safety Boundaries (replaces old II.F with maturity-triggered rules)

### Template Updates

- ✅ `.specify/templates/plan-template.md` - Constitution Check section updated
- ✅ `.specify/templates/spec-template.md` - Constitution Constraints section updated
- ✅ `.specify/templates/tasks-template.md` - Constitution-driven requirements section updated
- ⚠️ `.specify/templates/commands/*.md` - Review for outdated phase-specific references

### Follow-Up Actions

- Review all existing specs/plans/tasks for phase-specific language that now conflicts
- Update command files to reference conditional patterns instead of phase gates
- Consider adding ADR documenting the v1.0→v2.0 migration rationale

### Additional Refinements (2025-12-21)

- Trimmed excessive rationale text throughout (multi-bullet justifications → one-sentence summaries)
- Removed "Why This Matters" sections from principles
- Removed Appendix B (Technology Rationale Summary) - justification content moved out of constitution
- Changed table headers from "Rationale" to "Use Case" where appropriate

