# .github

Organisation-wide CI for megaeth-labs: composite actions consumed at `@main`
by every repository, and the workflow templates that show up under
"New workflow → By megaeth-labs".

- [`.github/actions/README.md`](.github/actions/README.md) — the catalogue of
  shared actions, how to consume one, how to change one.
- [`.github/actions/RELEASE.md`](.github/actions/RELEASE.md) — the release
  pipeline: candidate, settle, publish, publish targets.
- [`docs/RELEASING.md`](docs/RELEASING.md) — operator runbook for the release
  pipeline: the four flows, environments, dry run, troubleshooting.
- [`.github/actions/CLAUDE-CI.md`](.github/actions/CLAUDE-CI.md) — the Claude
  checks: PR review, label check, issue triage, interactive.
- `.github/actions/<action>/README.md` — one reference per action; the
  input, output, step and error tables are generated from `action.yml` by
  [`.github/scripts/action_docs.py`](.github/scripts/action_docs.py).
- Standalone building blocks: [`git-credentials`](.github/actions/git-credentials/README.md),
  [`export-env`](.github/actions/export-env/README.md),
  [`notify-lark`](.github/actions/notify-lark/README.md),
  [`merge-queue-skipper`](.github/actions/merge-queue-skipper/README.md),
  [`pr-lint`](.github/actions/pr-lint/README.md).
- [`workflow-templates/`](workflow-templates/) — the reference callers.
  [`.github/scripts/copy_templates.py`](.github/scripts/copy_templates.py)
  renders the release templates with one repository's values filled in.
- [`profile/`](profile/) — the organisation profile page.
- [`docs/github-org-admin-review-guide.md`](docs/github-org-admin-review-guide.md) —
  review guide for ambiguous GitHub organization administration requests.

`actions-test.yml` is the only gate between a change here and every
consumer's CI: unit tests of the helpers, an end-to-end drive of the actions
that can run without a repository, and the documentation check.

## App tokens: Maxwell and Gutenberg

Two GitHub Apps mint tokens through `actions/create-github-app-token`.
Maxwell is the CI app (`vars.MEGA_MAXWELL_CLIENT_ID`, `secrets.MEGA_MAXWELL_PK`):
it may write only pull requests and issues and never touches a release.
Gutenberg is the release app (`vars.MEGA_GUTENBERG_CLIENT_ID`,
`secrets.MEGA_GUTENBERG_PK`), from an organization variable and secret
with access granted to each consumer repository. It is minted only in
`release-candidate.yml`, `release-settle.yml` or `on-release.yml`; branch
and PR jobs declare no environment, while tagging, Release creation and
artifact upload use the review-gated `release` environment. Snapshots use
`snapshot`, outside that gate. The
[`app-token-lint`](.github/actions/app-token-lint/README.md) action enforces
this on every workflow change (rules L1-L6, listed with their messages in the
[runbook](docs/RELEASING.md#app-token-lint-errors)); run it locally with
`python3 .github/scripts/app_token_lint.py --repo <repo> <workflows dir>`.
