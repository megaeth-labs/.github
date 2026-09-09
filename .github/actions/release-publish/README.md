# Release Publish

`uses: megaeth-labs/.github/.github/actions/release-publish@main`

<!-- generated: description -->
Publish a settled release. Normally runs when a `chore/release-settle-vX.Y.Z` PR merges into its release branch (or, with `commit` + `version` given, on an explicit commit that `release-settle` in `direct` mode just made): creates the annotated tag `vX.Y.Z` at the merge commit (exactly once — refuses if it exists, or if the branch moved after the settle PR was opened) and publishes the GitHub Release with the changelog section as notes. This is the only place in the release flow that creates a tag; merging the settle PR is the approval. The default branch's changelog catches up in the next release candidate PR — nothing is back-merged. The consumer checks the repository out first (`fetch-depth: 0`, `persist-credentials: false`). Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `token` | yes |  | GitHub App installation token (e.g. the Maxwell app). The tag push must come from it so `push: tags` workflows (artifact builds) fire; the job's GITHUB_TOKEN would not trigger them. Also needs to be a bypass actor on the repository's tag ruleset. |
| `version_file` | yes |  | File holding the version (VERSION, Cargo.toml, pyproject.toml, package.json); the same value as in release-candidate. |
| `version_pattern` | no | `plain` | How the version is stored in `version_file`: plain, toml or json. |
| `changelog_file` | no | `CHANGELOG.md` | Changelog the entry is written to (Keep-a-Changelog style, newest first). |
| `release_branch_prefix` | no | `release-v` | Release branch name prefix; the branch is `<prefix>X.Y.Z`. |
| `commit` | no |  | Explicit commit to publish (full SHA), with `version`. Set by `release-settle` in `direct` mode; leave empty when triggered by the settle PR merging. The PR-specific guards (head/base names, author, drift marker) do not apply in this mode. |
| `version` | no |  | Version for the explicit-commit mode, X.Y.Z or vX.Y.Z. |
| `pr_author` | no | `mega-maxwell[bot]` | Login the settle PR must have been opened by — the app identity `release-settle` runs under. Stops a hand-made `chore/release-settle-*` branch from reaching the tag step. Empty disables the check. |
| `git_user_name` | no | `mega-maxwell[bot]` | Committer identity for the commits this action makes. |
| `git_user_email` | no | `290560214+mega-maxwell[bot]@users.noreply.github.com` | Committer email for the commits this action makes. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `version` | The normalised version, X.Y.Z. |
| `tag` | The tag created, vX.Y.Z. |
| `release_url` | URL of the GitHub Release. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Configure git auth
1. Guard
1. Create and push tag
1. Publish GitHub Release
1. Remove git auth *(only if `always()`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `explicit mode needs a full 40-hex commit and a version`
- `publish runs on a merged settle PR (pull_request closed, merged == true)`
- `head branch`
- `settle PR #$PR_NUMBER was opened by`
- `settle PR for v$version merged into`
- `settle PR body has no`
- `release branch drifted: settle PR settled $settled but the branch tip at merge was $parent. Re-run release-settle on the current tip.`
- `tag v$version already exists; a release is published once`
- `$FILE at $MERGE_SHA says $actual, expected $version`
<!-- /generated -->

## Example

PR mode, as in `workflow-templates/release-publish.yml` (triggered by the
settle PR closing; the job gate checks it merged and was opened by the app):

```yaml
- uses: megaeth-labs/.github/.github/actions/release-publish@main
  with:
    token: ${{ steps.app-token.outputs.token }}
    version_file: Cargo.toml
    version_pattern: toml
    changelog_file: CHANGELOG.md
```

In direct mode `release-settle` calls this action itself with `commit` and
`version`; a consumer never does.

## Notes

- Creates the annotated tag once (refuses if it exists) at the merge commit
  in PR mode — refusing if the merge's first parent is not the settled SHA
  recorded in the PR, or the PR was not opened by `pr_author` — or at
  `commit` in explicit mode; then publishes the GitHub Release, marked
  latest, with the changelog section as notes.
- The tag push comes from the app token so `push: tags` and `release`
  workflows fire; the app must bypass the `v*` tag ruleset.
- This workflow must exist on the release branch (it does when the branch
  was cut from a default branch that has it).
