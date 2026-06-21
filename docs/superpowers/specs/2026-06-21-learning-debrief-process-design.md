# Learning Debrief Process — Design

## Problem

Skiljo's implementation is largely carried out via subagent-driven development:
subagents execute tasks from a written plan, and the orchestrator (Claude,
in conversation with the project owner) reviews diffs and moves to the next
task. This is efficient for delivery, but it means a lot of real engineering
decisions — library choices, design tradeoffs, why an approach was picked
over alternatives — flow through the system without the project owner
necessarily absorbing them. As the project owner, leveling up as an engineer
by understanding the "ins and outs" of what's being built is itself a goal,
not just shipping working code.

## Goal

A structured, durable side-process that produces a written explanation
("debrief") after every implementation task, scoped to whatever in that task
is genuinely non-obvious — concepts, libraries, patterns, and design
rationale — so the project owner can read it independently of the
implementation conversation, at their own pace, without slowing delivery.

## Non-goals

- Not an interactive teaching/quiz mode — debriefs are written artifacts the
  owner reads on their own time, not real-time back-and-forth.
- Not tied to business/product rationale (BRD/PRFAQ) — scope is engineering
  concepts and decisions within the task itself, optionally citing
  `DESIGN_DOCUMENT.md` where a task implements a documented design decision.
- Not a replacement for the existing `.superpowers/sdd/` task briefs/reports
  (those are SDD's internal working artifacts, gitignored, and serve a
  different purpose: driving subagent execution and review, not teaching).

## Design

### Location and file structure

```
docs/learning/
  README.md              # index of all debrief files, in order
  GLOSSARY.md             # running concept glossary
  week1-task<N>-<slug>.md # one file per Week 1 task (none yet — Week 1 predates this process)
  week2-task1-llm-client-protocol.md
  week2-task2-structured-output-retry.md
  week2-task3-llm-call-logging.md
  ...
```

- `docs/learning/` sits alongside `docs/superpowers/` and is committed to
  git, so it persists across weeks and survives worktree merges back to
  `main`.
- File naming: `week<N>-task<M>-<slug>.md`, where `<N>` and `<M>` match the
  week/task numbering already used in `docs/superpowers/plans/`, and
  `<slug>` is a short kebab-case description of the task's deliverable.
- `docs/learning/README.md` lists every debrief file in commit order with a
  one-line description, so the owner can browse chronologically.

### Debrief content

Each debrief is scoped to what's non-obvious in that specific task — not a
rigid checklist that forces filler when a task is simple. The suggested
skeleton (sections omitted when not applicable):

- **What was built** — 2-4 sentence plain-language summary of the task's
  deliverable.
- **Key concepts** — libraries, language features, or patterns used in the
  task that aren't obvious, explained from the ground up (e.g., what a
  SQLAlchemy `sessionmaker` is and why the codebase creates one bound to an
  engine rather than constructing a session inline per call). When a
  concept already has a `GLOSSARY.md` entry, link to it instead of
  re-explaining; only add new prose for what's new or task-specific about
  this usage.
- **Why this way** — the design rationale for the approach taken, including
  alternatives considered or rejected, citing the relevant section of
  `DESIGN_DOCUMENT.md` or the task brief when the task implements a
  documented decision.
- **Where to look** — pointers (file paths, optionally line ranges) to the
  actual code changed in the task, so the owner reads the real
  implementation with the explanation in hand.

### Glossary

`docs/learning/GLOSSARY.md` is a single running file, entries sorted
alphabetically by term. Each entry: term, a 1-3 sentence definition, and a
link to the task debrief file containing the fuller explanation. A new
entry is added the first time a genuinely new concept is introduced in a
debrief. Subsequent debriefs reference existing entries by name/link rather
than re-explaining.

### Trigger and ownership

- A debrief is written automatically after every implementation task is
  completed and committed — no explicit request needed from the project
  owner.
- Writing the debrief is the orchestrator's responsibility, not a
  subagent's. The natural checkpoint is the same one where SDD already
  updates `.superpowers/sdd/progress.md`: after a task's code review passes
  and the commit lands, before moving to the next task. For tasks executed
  via plain `executing-plans` (no subagents), the equivalent checkpoint is
  immediately after that task's commit.

### Durability across sessions and future weeks

Two mechanisms, used together:

1. **`CLAUDE.md` convention.** A new section documents: the `docs/learning/`
   location and naming convention, the glossary mechanism, the trigger
   (after every task commit), and that it's the orchestrator's
   responsibility. Because `CLAUDE.md` is always loaded into context, this
   survives into any fresh session — including ones with no memory of this
   conversation.
2. **Explicit plan checklist step.** The remaining tasks in
   `docs/superpowers/plans/2026-06-21-week2-extraction-pipeline.md` (Task 3
   onward) get an added final checklist line: "Write learning debrief to
   `docs/learning/`." Future weekly plans (Week 3+), when generated via the
   `writing-plans` skill, should include the same step by default — noted
   in the `CLAUDE.md` section so it isn't lost.

### Backfill

Tasks 1 and 2 of the Week 2 plan are already complete (commits `5302c73`
and `301fb95`). Once this spec is approved, debriefs for both are written
immediately as a one-time catch-up, covering:

- Task 1: the `LLMClient` protocol and `AnthropicClient` implementation
  (`packages/core/src/skiljo_core/llm/base.py`,
  `packages/core/src/skiljo_core/llm/anthropic_client.py`).
- Task 2: structured output via tool-use with validation-retry (the
  `generate_structured` retry loop and its tests).

Task 3 (LLM call logging to Postgres) is currently in flight; its debrief is
written once it's committed, following the normal trigger going forward.

## Implementation scope

This is a documentation-only addition — no application code, schema, or CI
changes. The implementation plan covers:

1. Create `docs/learning/` with `README.md` and `GLOSSARY.md` skeletons.
2. Write backfilled debriefs for Week 2 Task 1 and Task 2.
3. Add the "Learning debriefs" section to `CLAUDE.md`.
4. Amend Task 3 onward in the Week 2 plan with the debrief checklist step.
5. Commit.

## Open questions

None — all structural decisions were resolved during brainstorming.
