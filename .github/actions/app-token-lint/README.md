# App Token Lint

`uses: megaeth-labs/.github/.github/actions/app-token-lint@main`

<!-- generated: description -->
Fail a workflow change that mints GitHub App tokens the wrong way. Maxwell (the CI app) may not request a `permission-<x>: write` other than pull-requests and issues; Gutenberg (the release app) may be minted only in a job of the `release` environment, or in a `publish` job when the token asks for exactly `permission-contents: read`; release workflows (those using the release-candidate, release-settle, release-publish or release-route actions, and on-release.yml) mint no Maxwell token, never name their own repository in a read-only dependency token, and never use `mega-maxwell[bot]` as a git identity or PR author filter; and `environment: release` appears only in release-candidate.yml, release-settle.yml and on-release.yml. Violations are reported as `::error file=<path>::<job>/<step>: <rule>: <message>`; unreadable or malformed YAML is an error too. No network.
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
  pull-requests and issues; **L2** Gutenberg tokens need `environment: release`
  (or `publish` with exactly `permission-contents: read`); **L3** release
  workflows mint no Maxwell token and no read-only dependency token naming
  their own repository; **L4** release workflows never use `mega-maxwell[bot]`;
  **L5** `environment: release` only in `release-candidate.yml`,
  `release-settle.yml` and `on-release.yml`; **L6** a Maxwell or Gutenberg
  token, and any app token in a release job, requests at least one
  `permission-<x>` (without one it gets every permission of the installation).
- A token step is a step using `actions/create-github-app-token`; Maxwell is
  recognised by `MEGA_MAXWELL_`, `CI_APP_ID` or `MEGA_CI_APP_PK` in
  `client-id`, `app-id` or `private-key`, Gutenberg by `RELEASE_APP_`.
- A permission that is not a literal value (an expression) cannot be checked
  and counts as a violation for a Maxwell token.
- A path that does not exist, a directory without `*.yml`/`*.yaml` files and
  malformed YAML are errors, never a clean pass.
- The script is `.github/scripts/app_token_lint.py`; it needs no network and
  runs locally as `python3 .github/scripts/app_token_lint.py --repo <name> <paths>`.
