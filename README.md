# .github

Organisation-wide CI for megaeth-labs: composite actions consumed at `@main`
by every repository, and the workflow templates that show up under
"New workflow → By megaeth-labs".

- [`.github/actions/RELEASE.md`](.github/actions/RELEASE.md) — the release
  pipeline: candidate, settle, publish, publish targets; how it works, how to
  install it in a repository, options, recovery.
- [`.github/actions/README.md`](.github/actions/README.md) — the Claude CI
  actions: PR review, label check, issue triage, interactive.
- [`workflow-templates/`](workflow-templates/) — the reference callers.
- [`profile/`](profile/) — the organisation profile page.

`actions-test.yml` is the only gate between a change here and every
consumer's CI; it runs the unit tests of the text helpers and drives the
actions that can be exercised without a repository.
