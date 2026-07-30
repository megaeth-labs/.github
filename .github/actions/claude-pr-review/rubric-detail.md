# Detailed review checks (conditional)

Read only the section(s) the diff actually touches — see "Routing to detailed checks" in the
rubric. These are line-level checks that would clutter a review if applied everywhere. Keep
findings here at `[Minor]`/`[Nit]` unless they cause incorrect behavior, in which case escalate.

## Persistence

- **Crash-consistency:** on-disk writes must survive a crash mid-write — write to a temp file
  and atomically `rename()` into place; never leave a half-written file on crash or power loss.
- **Atomic multi-step persists:** a sequence that must be all-or-nothing (e.g. clean-old +
  write-new) should be one atomic operation; a crash between steps must not leave inconsistent
  on-disk state.
- **No silent corruption on serialize:** don't write `…unwrap_or_default()` bytes — empty or
  default bytes silently produce a corrupt record that later parses as a wrong-but-valid value.
- **Don't gold-plate internal artifacts:** for non-user-facing on-disk output, optimize for
  not-misleading over pretty (e.g. don't spend effort pretty-printing an internal dump).

## Unit-safety

- **Annotate ambiguous integers:** two same-typed integers with different units in one
  struct or signature is a trap — put the unit in the name or a doc so durations and
  comparisons can't be miscomputed.
- **One conversion choke point:** route scaling conversions (`*1000` / `/1000`, ms↔ns, etc.)
  through a single named helper with a `_lossy` suffix when it truncates, so the lossy step is
  visible at every call site and a fix is a one-file diff.

## Test-&-perf-surface

- **Assertion placement:** put an assertion where the test or fuzzer actually observes the
  condition — not after an early `return Err` that makes it tautologically true (the failing
  case is then never exercised).
- **Evidence for perf-shaped / hot-path changes:** require a benchmark, and an equivalence test
  pinning new == old behavior, before trusting an optimization or a hot-path restructure.
- **Dead or test-only scaffolding is a trapdoor:** a `Default`/`Option`/bootstrap field or
  method with zero production callers isn't merely unused — it's a latent footgun a future
  caller can trip. Confirm zero callers, then delete it.

## CI-workflow-security

- **No untrusted input in `run:` blocks:** never interpolate a PR title/body/branch or other
  attacker-controlled value straight into a shell step — pass it through `env:` and reference
  `"$VAR"`, or feed secrets via `--password-stdin`, so a crafted value can't inject commands.
- **Least-privilege the token:** set `persist-credentials: false` on `checkout` when later steps
  don't need the token, keep `GITHUB_TOKEN`/job permissions minimal, and pin third-party actions
  to a full commit SHA when a broad-scoped token is in play.
- **Teardown must run on failure:** cleanup of enclaves/containers/temp infra belongs on an
  `if: always()` / `ERR` / `EXIT` trap path, not a plain step that `set -e` skips after an
  earlier failure. Prefer `if: !cancelled()` over `always()` when a cancelled run must not
  resurrect work.
- **Guard comment/label triggers:** a workflow keyed on a comment marker or label must check the
  actor's association/author — otherwise any outsider triggers the privileged path by echoing
  the marker.
