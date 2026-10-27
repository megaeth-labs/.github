# Release Route

`uses: megaeth-labs/.github/.github/actions/release-route@main`

<!-- generated: description -->
Route a push or manual dispatch to cut, refresh, publish or skip using merged release PR metadata. Read-only; uses the job token, not a release App secret. Requires a checkout with full history and persist-credentials disabled.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `kind` | yes |  | Release flow to route: candidate or settle. |
| `github_token` | no | `${{ github.token }}` | Read-only job token with contents and pull-requests read. |
| `pr_author` | no | `mega-gutenberg[bot]` | Expected author of candidate and settle PRs. |
| `version_file` | yes |  | File holding the release version. |
| `version_pattern` | no | `plain` | Version file format: plain, toml or json. |
| `release_branch_prefix` | no | `release-v` | Release branch prefix before X.Y.Z. |
| `version` | no |  | Optional version filter for manual dispatch. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `action` | Next action: cut, refresh, publish or skip. |
| `reason` | Why this action was selected. |
| `version` | Normalized release version, when routing one push. |
| `release_branch` | Release branch for the pushed version. |
| `commit` | Pushed commit for cut, refresh or publish. |
| `pr_number` | Merged release PR number, when matched. |
| `targets` | Compact JSON array of refresh targets. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Route
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `release-route needs full history; check out with fetch-depth: 0`
<!-- /generated -->

## Example

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
    persist-credentials: false
- uses: megaeth-labs/.github/.github/actions/release-route@main
  id: route
  with:
    kind: settle
    version_file: VERSION
```

## Notes

The calling job needs `contents: read` and `pull-requests: read`.
