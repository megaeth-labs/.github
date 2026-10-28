# App Token Lint

`uses: megaeth-labs/.github/.github/actions/app-token-lint@main`

<!-- generated: description -->
Fail a workflow change that mints GitHub App tokens the wrong way. Maxwell (the CI app) may not request a `permission-<x>: write` other than pull-requests and issues; Gutenberg (the release app) reads `MEGA_GUTENBERG_CLIENT_ID` and `MEGA_GUTENBERG_PK` from organization scope and may be minted only in `release-candidate.yml`, `release-settle.yml` or `on-release.yml`, with or without an environment and whatever contents permission the job needs, because L6 still forces an explicit `permission-*` list either way; release workflows (those using the release-candidate, release-settle, release-publish or release-route actions, and on-release.yml) mint no Maxwell token, never name their own repository in a read-only dependency token, and never use `mega-maxwell[bot]` as a git identity or PR author filter; and the one-reviewer `release` environment gates only tagging, Release creation and artifact upload. Violations are reported as `::error file=<path>::<job>/<step>: <rule>: <message>`; unreadable or malformed YAML is an error too. No network.
<!-- /generated -->

Standalone action; no family guide.

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `paths` | no | `.github/workflows` | Workflow files or directories of them to lint, separated by whitespace (no spaces inside a path). The repository name used by the own-repository check comes from `GITHUB_REPOSITORY`. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
This action sets no outputs.
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Install PyYAML if missing
1. Lint App token usage
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
Its shell steps report no errors of their own; failures come from the actions and tools it calls.
<!-- /generated -->

## Example

Lint a repository's own workflows on every pull request:

```yaml
on:
  pull_request:
    paths: [".github/workflows/**"]

jobs:
  app-token-lint:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: megaeth-labs/.github/.github/actions/app-token-lint@main
```

The action reads `.github/workflows` by default; pass `paths:` to lint
another directory or several, e.g. `paths: .github/workflows workflow-templates`.

## Notes

- Rules, in the order violations name them: **L1** Maxwell tokens write only
  pull-requests and issues; **L2'** Gutenberg tokens may be minted only in
  `release-candidate.yml`, `release-settle.yml` or `on-release.yml`,
  with contents write allowed even without an
  environment; **L3** release
  workflows mint no Maxwell token and no read-only dependency token naming
  their own repository; **L4** release workflows never use `mega-maxwell[bot]`;
  **L5** `environment: release` only in the same exact three files as L2'
  (including in non-release workflows); **L6** a Maxwell or Gutenberg
  token, and any app token in a release job, requests at least one
  `permission-<x>` (without one it gets every permission of the installation).
- The shared L2'/L5 allowlist matches the shipped release workflow templates
  exactly; a new `release-publish-` filename grants no token or gated-environment
  rights. Neither `release-publish.yml` nor `release-publish-rust-crates.yml`
  is a shipped workflow template.
- A token step is a step using `actions/create-github-app-token`; Maxwell is
  recognised by `MEGA_MAXWELL_`, `CI_APP_ID` or `MEGA_CI_APP_PK` in
  `client-id`, `app-id` or `private-key`, Gutenberg by `MEGA_GUTENBERG_`.
- A permission that is not a literal value (an expression) cannot be checked
  and counts as a violation for a Maxwell token.
- A path that does not exist, a directory without `*.yml`/`*.yaml` files and
  malformed YAML are errors, never a clean pass.
- The script is `.github/scripts/app_token_lint.py`; it needs no network and
  runs locally as `python3 .github/scripts/app_token_lint.py --repo <name> <paths>`.
