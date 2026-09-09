# Release Candidate

`uses: megaeth-labs/.github/.github/actions/release-candidate@main`

<!-- generated: description -->
Start a release (trunk-first). `stage: propose` bumps the version file on the default branch, drafts this release's changelog entry (dated at settle) from the commits since the previous tag, syncs the previous release's entry from its tag, and opens a `chore/release-candidate-vX.Y.Z` PR; `stage: cut`, run when that PR merges, creates `release-vX.Y.Z` at the merge commit. No tag is created at either stage — tags come from release-publish, once, at settlement. Run as a step in a job the consumer owns; the consumer checks the repository out first (`fetch-depth: 0`, `persist-credentials: false`). Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `stage` | yes |  | `propose` (on workflow_dispatch) or `cut` (on the candidate PR merging). |
| `token` | yes |  | Token that authors the PR and creates the branch. Must be a GitHub App installation token (e.g. the Maxwell app) so the PR triggers CI; the job's GITHUB_TOKEN does not. |
| `version` | no |  | Version to release, X.Y.Z or vX.Y.Z. Required for `propose`. |
| `version_file` | yes |  | File holding the version (VERSION, Cargo.toml, pyproject.toml, package.json). |
| `version_pattern` | no | `plain` | How the version is stored in `version_file`: plain, toml or json. |
| `bump_command` | no |  | Optional shell command run after `version_file` is rewritten, for anything else that must move with the version: lockfiles (`cargo update --workspace`), path-dependency versions, generated files. Runs with `OLD_VERSION` and `NEW_VERSION` in the environment, in the repository root, under `bash -euo pipefail`. Whatever it changes is committed with the bump. Install any toolchain it needs in the calling job before this action. |
| `release_branch_prefix` | no | `release-v` | Release branch name prefix; the branch is `<prefix>X.Y.Z`. |
| `changelog_file` | no | `CHANGELOG.md` | Changelog to draft into (Keep-a-Changelog style, newest first). Empty disables changelog handling. |
| `pr_labels` | no |  | Comma-separated labels for the candidate PR. |
| `pr_author` | no | `mega-maxwell[bot]` | Login the candidate PR must have been opened by for `cut` to proceed — the app identity `propose` runs under. Stops a hand-made `chore/release-candidate-*` branch from driving the cut. Empty disables the check. |
| `git_user_name` | no | `mega-maxwell[bot]` | Committer identity for the bump commit. |
| `git_user_email` | no | `290560214+mega-maxwell[bot]@users.noreply.github.com` | Committer email for the commits this action makes. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `version` | Normalised X.Y.Z. |
| `pr_url` | `propose`: URL of the candidate PR. |
| `release_branch` | `cut`: the release branch created. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Resolve version
1. Configure git auth
1. Guard (propose) *(only if `inputs.stage == 'propose'`)*
1. Bump version file *(only if `inputs.stage == 'propose'`)*
1. Run bump command *(only if `inputs.stage == 'propose' && inputs.bump_command != ''`)*
1. Draft changelog *(only if `inputs.stage == 'propose' && inputs.changelog_file != ''`)*
1. Remove git auth before opening the PR *(only if `inputs.stage == 'propose'`)*
1. Drop a stale candidate branch *(only if `inputs.stage == 'propose'`)*
1. Open candidate PR — `peter-evans/create-pull-request` *(only if `inputs.stage == 'propose'`)*
1. Cut release branch *(only if `inputs.stage == 'cut'`)*
1. Remove git auth *(only if `always()`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `stage must be propose or cut, got`
- `release candidates start from the default branch ($default); this run is on $GITHUB_REF_NAME`
- `$VERSION is not newer than the latest tag ${latest:-<none>}`
- `tag v$VERSION already exists`
- `branch ${PREFIX}${VERSION} already exists`
- `after bump_command, $FILE reads $actual, expected $NEW_VERSION`
- `cut runs on a merged candidate PR (pull_request closed, merged == true)`
- `candidate PR #$PR_NUMBER was opened by`
- `$FILE at $MERGE_SHA says $actual, expected $VERSION`
- `branch $branch already exists`
<!-- /generated -->

## Example

The `propose` job on a dispatch, the `cut` job on the candidate PR merging;
both from `workflow-templates/release-candidate.yml`:

```yaml
- uses: megaeth-labs/.github/.github/actions/release-candidate@main
  with:
    stage: propose            # or: cut
    token: ${{ steps.app-token.outputs.token }}
    version: ${{ inputs.version }}   # propose only
    version_file: Cargo.toml
    version_pattern: toml
    changelog_file: CHANGELOG.md
    bump_command: cargo update --workspace   # propose only; needs the toolchain installed first
```

## Notes

- `propose` bumps the version file, runs `bump_command` with `OLD_VERSION`
  and `NEW_VERSION` set, drafts the `## vX.Y.Z` changelog entry from the
  merged PR titles since the last `v*` tag, syncs the previous release's
  entry from its tag, drops a stale `chore/release-candidate-X.Y.Z` branch
  (unless its PR is still open, in which case that PR is updated, with a
  force push of its branch), and opens the candidate PR.
- `cut` runs when that PR merges and creates `<release_branch_prefix>X.Y.Z`
  at the merge commit; it refuses a PR not opened by `pr_author`.
- `token` must be an App installation token: a `GITHUB_TOKEN` push would not
  trigger the consumer's CI on the candidate PR.
- The full flow, installation and recovery: [RELEASE.md](../RELEASE.md).
