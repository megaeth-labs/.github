# Release Publish

`uses: megaeth-labs/.github/.github/actions/release-publish@main`

<!-- generated: description -->
Publish a settled release. Runs on a push to `release-vX.Y.Z` (the consumer passes the `commit` and `pr_number` that `release-route` resolved for the push). Re-verifies the merged `chore/release-settle-vX.Y.Z` PR through the API — merged, merge commit equals the pushed commit, head/base names, author, and the settled-SHA marker against the merge commit's parent — then creates the annotated tag `vX.Y.Z` at that commit and publishes the GitHub Release with the changelog section as notes. A tag already at the commit without a Release (a run that died between the two steps) is resumed: the tag step is skipped and the Release is still created. A tag at the commit with its Release already there is a retry of a finished run and exits 0 with a notice; a tag at any other commit refuses, because a release is published once. A tag push or Release create that loses a race to a concurrent run of the same publish keeps the winner's, if it is at this commit. This is the only place in the release flow that creates a tag; merging the settle PR is the approval. The default branch's changelog catches up in the next release candidate PR — nothing is back-merged. The consumer checks the repository out first (`fetch-depth: 0`, `persist-credentials: false`). Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `token` | yes |  | mega-gutenberg installation token minted in an `environment: release` job; gutenberg is the bypass actor on the `v*` tag ruleset, and a Release it creates fires `release: published` workflows. |
| `version_file` | yes |  | File holding the version (VERSION, Cargo.toml, pyproject.toml, package.json); the same value as in release-candidate. |
| `version_pattern` | no | `plain` | How the version is stored in `version_file`: plain, toml or json. |
| `changelog_file` | no | `CHANGELOG.md` | Changelog the entry is written to (Keep-a-Changelog style, newest first). |
| `release_branch_prefix` | no | `release-v` | Release branch name prefix; the branch is `<prefix>X.Y.Z`. |
| `commit` | yes |  | The pushed commit to publish (full SHA), as resolved by `release-route`; it must be the settle PR's merge commit. |
| `pr_number` | yes |  | Number of the merged settle PR for `commit`, as resolved by `release-route`. |
| `pr_author` | no | `mega-gutenberg[bot]` | Login the settle PR must have been opened by — the app identity `release-settle` runs under. Stops a hand-made `chore/release-settle-*` branch from reaching the tag step. Empty disables the check. |
| `git_user_name` | no | `mega-gutenberg[bot]` | Committer identity for the commits this action makes. |
| `git_user_email` | no | `348780249+mega-gutenberg[bot]@users.noreply.github.com` | Committer email for the commits this action makes. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `version` | The normalised version, X.Y.Z. |
| `tag` | The tag published, vX.Y.Z (created now, or already at the commit from an interrupted run). |
| `release_url` | URL of the GitHub Release (created now, or found by a retry of a finished run). |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Configure git identity
1. Guard
1. Create and push tag *(only if `steps.guard.outputs.tag_exists != 'true'`)*
1. Publish GitHub Release *(only if `steps.guard.outputs.published != 'true'`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `publish needs a full 40-hex commit and a numeric pr_number (the release-route outputs)`
- `settle PR #$PR_NUMBER is not merged; publish only follows a merged settle PR`
- `settle PR #$PR_NUMBER merged as`
- `head branch`
- `settle PR #$PR_NUMBER was opened by`
- `settle PR for v$version merged into`
- `settle PR body has no`
- `release branch drifted: settle PR settled $settled but the branch tip at merge was $parent. Re-run release-settle on the current tip.`
- `tag $tag already exists (at $(git rev-parse`
- `$FILE at $MERGE_SHA says $actual, expected $version`
- `could not push $TAG; the remote tag is at $(git rev-parse`
- `could not create the Release for $TAG`
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

- Creates the annotated tag once (refuses if it exists elsewhere; resumes or
  no-ops if it is already at this commit) at the merge commit
  in PR mode — refusing if the merge's first parent is not the settled SHA
  recorded in the PR, or the PR was not opened by `pr_author` — or at
  `commit` in explicit mode; then publishes the GitHub Release, marked
  latest, with the changelog section as notes.
- The tag push comes from the app token so `push: tags` and `release`
  workflows fire; the app must bypass the `v*` tag ruleset.
- This workflow must exist on the release branch (it does when the branch
  was cut from a default branch that has it).
