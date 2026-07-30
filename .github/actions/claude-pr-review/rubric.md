# MegaETH PR Review Rubric (shared baseline)

A consumer repo's `REVIEW.md` / `CLAUDE.md` / `AGENTS.md` override or extend anything here;
defer to them on conflict. This is the general baseline only.

## Stance (governs everything below)

- Review **structure and design, not lines**. The deepest finding makes a special case
  disappear; the shallowest renames a variable. Spend attention high.
- The goal is improving code health over time — approve "better" even when not "perfect."
  Critique the code, not the person, and always say _why_.
- **Personal taste or style is never a change request.** If the formatter, a linter, the type
  checker, or the author's reasonable judgment can own it, stay silent.
- Severity is **leverage** (how much the design improves), not effort to spot. Default to
  silence — a clean PR gets a clean verdict, not invented findings.

## Lenses — judge in this order; the earlier the lens, the higher its leverage

### 1. Design & data structures

Are the core types right? Bad code around good data structures is fixable; the reverse is not.

- Encode invariants in the type so the compiler catches misuse — prefer a newtype/enum/`OnceCell`
  over a primitive-with-sentinel. A config knob or `Default` with only one correct value is a
  footgun; remove it.
- Does each piece live where its responsibility lives? One concept = one type across all its
  consumers, not a parallel type per subsystem. Decompose god-structs (pure logic that returns
  effects + a thin orchestrator).
- Prefer eliminating an edge case through better design over adding a conditional.
- Keep it simple — can the number of concepts be cut? An abstraction is _earned_ only if it
  (a) hides an impl detail, (b) enables a test fake, **and (c) keeps its generic bounds
  confined** — otherwise inline it; a single call site rarely earns a new trait or indirection.
- Respect existing framework/library conventions rather than replacing them.

### 2. Correctness & safety

- Edge cases, off-by-ones, and races; extra scrutiny for consensus-/protocol-/wire-critical or
  backward-compat-sensitive code.
- **Fail loud over silently-wrong:** an explicit error beats a quietly wrong value. A _fatal_
  condition must actually terminate the unit, not just the loop that observed it.
- Errors are handled or their ignore is justified with a comment; no silently dropped sends or
  join-errors; prefer typed error enums over opaque/stringly errors.
- Unsafe code carries a `SAFETY` comment justifying its invariants. No unhandled concurrency
  hazards — shared mutable state, TOCTOU, deadlocks.
- **Bound every queue and buffer.** An unbounded channel, work queue, retry backlog, or
  per-connection buffer is a memory-DoS — one slow consumer or hostile peer grows it without
  limit. Cap depth (with a drop or backpressure policy) and apply size checks before
  accumulating bytes; keep metric label sets bounded too (no unbounded-cardinality labels).

### 3. Surface stewardship

What does this disturb that others depend on?

- Call out breaking changes to any published or public API/contract explicitly; public API or
  interface changes carry a documented rationale.
- Minimize the diff to vendored/forked/upstream files — even comment-only drift costs rebase
  surface; keep customizations in our own modules.
- Don't change the semantics of an existing function — add a new one.
- Treat stable wire, on-disk, and public surfaces as sacred.

### 4. Change & operate

Can the next person change and run this safely?

- **Tests:** present for new/changed logic; deterministic (no sleep/wall-clock); assert exact
  values and specific error variants (not `is_ok`/truthiness); cover side effects and the
  absence of unintended change. If logic is hard to test, that's a design signal (split pure
  logic from I/O). A bool param every caller passes identically is an untested dimension. Don't
  build the expected value from the same primitive under test.
- **Naming & docs:** names describe state/intent, not effect or serialization format; drop
  redundant qualifiers. Comments and docs explain _why_, not _what_; new modules carry a
  one-line orientation. A missing or misleading doc on a non-obvious invariant is a real gap.
- **Observability:** error variants carry the disagreeing values; loss/drop logs carry the
  correlating key; fail-open paths expose a scrape-visible counter; long-running spawned tasks
  get a tracing span; never print secrets into `--help`. Logging uses structured fields at
  appropriate levels (not string interpolation); recurring counts/durations are metrics, not logs.
- **Doc proximity:** implementation mechanics live with the code; design docs hold
  architecture/rationale and link to code rather than restating it. Flag the same fact
  duplicated across homes — pick one authoritative home.

## Do NOT flag

- Formatting, lint, or type errors already owned by the repo's formatter/linter/type-checker —
  never spend review effort on style.
- Redundant guards that aid readability; empirically-tuned constants/thresholds.
- Anything already addressed in the diff (read the full diff first).
- Avoid bikeshedding, nitpick avalanches, gatekeeping on style or hypotheticals, and
  manufacturing feedback. If the PR is clean, say so.

## How to deliver

- **Propose the concrete alternative** (a `suggestion` block, a sketch, a rename target) — not
  just a complaint. For a consequential design ask, note the option you considered and rejected
  and why.
- Open with what's genuinely good before the asks.
- Calibrate: blocking (correctness / security / breakage / consensus) vs. should-fix vs.
  follow-up. Route non-blocking design improvements to a follow-up suggestion; don't block.
- A finding's altitude should match its severity — a `[Nit]` that's really a structural concern
  is mis-tagged.
- Confirm the PR title follows Conventional Commits and the description explains what & why;
  flag a stale or misleading title/description after new commits.

## Routing to detailed checks (read on demand)

Before finalizing, if the diff touches any of these areas, read the matching section of
`.claude-review/rubric-detail.md` and apply it; skip areas the diff does not touch (these are
line-level checks — do not load them when irrelevant):

- **Persistence / on-disk writes / serialization** → §Persistence
- **Unit / time / scaling math (ratios, conversions, timestamps)** → §Unit-safety
- **Tests, fuzzers, or fault-injection harnesses; perf-shaped changes** → §Test-&-perf-surface
- **CI/CD workflows or composite actions (`.github/workflows`, `action.yml`)** → §CI-workflow-security
