# Release Candidate

`uses: megaeth-labs/.github/.github/actions/release-candidate@main`

<!-- generated: description -->
Start a release (trunk-first). `stage: propose` bumps the version file on the default branch, drafts this release's changelog entry (dated at settle) from the commits since the previous tag, syncs the previous release's entry from its tag, and opens a `chore/release-candidate-vX.Y.Z` PR; `stage: cut`, run on the push that merged that PR (the consumer passes the `commit` and `pr_number` outputs of `release-route`), re-reads the PR through the API, refuses anything but a merged, gutenberg-authored candidate into the default branch, and creates `release-vX.Y.Z` at the merge commit (a retry that finds it already there is a no-op; at any other commit it refuses). No tag is created at either stage — tags come from release-publish, once, at settlement. `base_commit` releases a commit that is not the tip of the default branch: `propose` cuts the release branch there itself, carries the default branch's release workflows onto it, and points the candidate PR at it; that PR merges into the release branch, so `cut` never runs for it. Run as a step in a job the consumer owns, in `environment: release`; the consumer checks the repository out first (`fetch-depth: 0`, `persist-credentials: false`). Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `stage` | yes |  | `propose` (on workflow_dispatch) or `cut` (on the candidate PR merging). |
| `token` | yes |  | mega-gutenberg installation token (contents, pull-requests, workflows write) minted in an `environment: release` job; it pushes the candidate branch, opens the PR (so CI runs) and creates the release branch. |
| `dependency_token` | no |  | Read-only token for bump_command's private dependencies. Required when bump_command is set; it never falls back to token, so the command does not run with the release token. |
| `commit` | no |  | The merge commit of the candidate PR (the `commit` output of `release-route`). Required for `cut`; the release branch is created at it. |
| `pr_number` | no |  | The candidate PR number (the `pr_number` output of `release-route`). Required for `cut`; the PR is re-read through the API, not trusted from the event. |
| `release_workflows` | no | `.github/workflows/release-settle.yml .github/workflows/on-release.yml` | Newline- or space-separated workflow paths `propose` with `base_commit` copies from the default branch onto the old tree (a path absent on the default branch is skipped), and it deletes `.github/workflows/release-publish.yml`. Workflows run from the pushed ref's tree, so a branch cut at an older commit would otherwise run pre-migration release workflows. |
| `version` | no |  | Version to release, X.Y.Z or vX.Y.Z. Required for `propose`. |
| `base_commit` | no |  | The commit to release, for `propose`, when it must not be the tip of the default branch. Any commit-ish the checkout can resolve (a full SHA, a tag, `origin/main~3`). It must be reachable from the default branch, or sit on the latest `v*` release line (from the merge-base with trunk through that tag), so a hotfix of the current tag works even though settlement left the tag off trunk. Empty (the default) is the trunk-first flow: the candidate PR merges into the default branch and `cut` creates the release branch at that merge commit. Set, `propose` creates the release branch at this commit and opens the candidate PR against that branch, because merging it into the default branch would take the commits this release is leaving out; the default branch is then untouched and `cut` never runs. The version must still be newer than the newest `v*` tag in the repository. |
| `version_file` | yes |  | File holding the version (VERSION, Cargo.toml, pyproject.toml, package.json). |
| `version_pattern` | no | `plain` | How the version is stored in `version_file`: plain, toml or json. |
| `bump_command` | no |  | Optional shell command run after `version_file` is rewritten, for anything else that must move with the version: lockfiles (`cargo update --workspace`), path-dependency versions, generated files. Runs with `OLD_VERSION` and `NEW_VERSION` in the environment, in the repository root, under `bash -euo pipefail`. Whatever it changes is committed with the bump. Install any toolchain it needs in the calling job before this action. |
| `release_branch_prefix` | no | `release-v` | Release branch name prefix; the branch is `<prefix>X.Y.Z`. |
| `changelog_file` | no | `CHANGELOG.md` | Changelog to draft into (Keep-a-Changelog style, newest first). Empty disables changelog handling. |
| `pr_labels` | no |  | Comma-separated labels for the candidate PR. |
| `pr_author` | no | `mega-gutenberg[bot]` | Login the candidate PR must have been opened by for `cut` to proceed — the app identity `propose` runs under. Stops a hand-made `chore/release-candidate-*` branch from driving the cut. Empty disables the check. |
| `git_user_name` | no | `mega-gutenberg[bot]` | Committer identity for the bump commit. |
| `git_user_email` | no | `348780249+mega-gutenberg[bot]@users.noreply.github.com` | Committer email for the commits this action makes. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `version` | Normalised X.Y.Z. |
| `pr_url` | `propose`: URL of the candidate PR. |
| `release_branch` | The release branch: created by `cut`, or by `propose` when `base_commit` is set. |
| `base_commit` | `propose` with `base_commit`: that commit-ish resolved to a full SHA. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Resolve version
1. Configure git identity
1. Guard (propose) *(only if `inputs.stage == 'propose'`)*
1. Cut the release branch at the base commit (propose) *(only if `inputs.stage == 'propose' && inputs.base_commit != ''`)*
1. Carry the release workflows (propose) *(only if `inputs.stage == 'propose' && inputs.base_commit != ''`)*
1. Bump version file *(only if `inputs.stage == 'propose'`)*
1. Run bump command *(only if `inputs.stage == 'propose' && inputs.bump_command != '' && steps.bump.outputs.skipped != 'true'`)*
1. Draft changelog *(only if `inputs.stage == 'propose' && inputs.changelog_file != '' && steps.bump.outputs.skipped != 'true'`)*
1. Open candidate PR *(only if `inputs.stage == 'propose'`)*
1. Cut release branch *(only if `inputs.stage == 'cut'`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `cut needs the pr_number input (the release-route output)`
- `stage must be propose or cut, got`
- `release candidates start from the default branch ($default); this run is on $GITHUB_REF_NAME`
- `$VERSION is not newer than the latest tag ${latest:-<none>}`
- `tag v$VERSION already exists`
- `base_commit $BASE_COMMIT is not a commit in this checkout; check the repository out with fetch-depth: 0`
- `base_commit $base is not reachable from the default branch ($default); a release must ship code that landed on trunk`
- `branch $branch already exists: v$VERSION was already cut from its merged candidate, so there is nothing left to propose; settle it from $branch`
- `branch $branch already exists at $existing, which does not contain base_commit $base`
- `could not create $BRANCH at $checkout (it is now at`
- `bump_command needs a separate dependency_token, so the command never runs with the release token`
- `after bump_command, $FILE reads $actual, expected $NEW_VERSION`
- `could not close the open candidate PR #$number ($url)`
- `could not delete $head, and no open PR owns it`
- `could not push $head`
- `could not open the candidate PR for $head`
- `cut needs the commit and pr_number inputs (the release-route outputs)`
- `candidate PR #$PR_NUMBER has not been merged; cut only runs for a merged candidate`
- `candidate PR #$PR_NUMBER merged as`
- `PR #$PR_NUMBER head`
- `candidate PR #$PR_NUMBER targets`
- `candidate PR #$PR_NUMBER was opened by`
- `$FILE at $COMMIT says $actual, expected $VERSION`
- `could not create $branch at $COMMIT`
- `branch $branch already exists at $existing, not at the candidate merge commit $COMMIT; refusing to move it`
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
  entry from its tag, and opens the candidate PR from a new
  `chore/release-candidate-X.Y.Z` branch. It never rewrites a branch: a
  candidate PR still open for that version is closed with a comment saying a
  fresh candidate supersedes it, its branch is deleted, and the new commit is
  pushed as a new ref. A retry, or a run racing another, converges on one
  branch and one open PR (a branch or PR the other run made first is kept).
  The branch is deleted on merge only by the repository's "Automatically
  delete head branches" setting; the step log says which applies.
- `cut` runs when that PR merges and creates `<release_branch_prefix>X.Y.Z`
  at the merge commit; it refuses a PR not opened by `pr_author`. A retry
  that finds the branch already at that commit exits 0 with a notice; at
  any other commit it refuses and names both SHAs.
- `token` must be an App installation token: a `GITHUB_TOKEN` push would not
  trigger the consumer's CI on the candidate PR.
- The full flow, installation and recovery: [RELEASE.md](../RELEASE.md).
