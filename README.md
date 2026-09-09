# .github

Organisation-wide CI for megaeth-labs: composite actions consumed at `@main`
by every repository, and the workflow templates that show up under
"New workflow → By megaeth-labs".

- [`.github/actions/README.md`](.github/actions/README.md) — the catalogue of
  shared actions, how to consume one, how to change one.
- [`.github/actions/RELEASE.md`](.github/actions/RELEASE.md) — the release
  pipeline: candidate, settle, publish, publish targets.
- [`.github/actions/CLAUDE-CI.md`](.github/actions/CLAUDE-CI.md) — the Claude
  checks: PR review, label check, issue triage, interactive.
- `.github/actions/<action>/README.md` — one reference per action; the
  input, output, step and error tables are generated from `action.yml` by
  [`.github/scripts/action_docs.py`](.github/scripts/action_docs.py).
- [`workflow-templates/`](workflow-templates/) — the reference callers.
- [`profile/`](profile/) — the organisation profile page.

`actions-test.yml` is the only gate between a change here and every
consumer's CI: unit tests of the helpers, an end-to-end drive of the actions
that can run without a repository, and the documentation check.
