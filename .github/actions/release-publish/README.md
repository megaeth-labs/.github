# Release Publish

`uses: megaeth-labs/.github/.github/actions/release-publish@main`

<!-- generated: description -->
Publish a settled release. By default, runs on a push to `release-vX.Y.Z` (the consumer passes the `commit` and `pr_number` that `release-route` resolved for the push). Re-verifies the merged `chore/release-settle-vX.Y.Z` PR through the API — merged, merge commit equals the pushed commit, head/base names, author, and the settled-SHA marker against the merge commit's parent. With `settle_source: dispatch`, verifies the merged candidate PR's merge SHA, head, base and author, and that `release_branch` still points at `commit` for a fresh publish, or contains `commit` when resuming an existing tag; repeats this state check immediately before tagging. Then creates the annotated tag `vX.Y.Z` at that commit and publishes the GitHub Release with the changelog section as notes. A tag already at the commit without a Release (a run that died between the two steps) is resumed: the tag step is skipped and the Release is still created. Re-run the push-triggered workflow for the settle-PR shape, or dispatch for the direct shape. A tag at the commit with its Release already there is a retry of a finished run and exits 0 with a notice; a tag at any other commit refuses, because a release is published once. A version that is not newer than every other `vX.Y.Z` tag (the rule `release-route` applies) is refused before the tag, and the Release is marked latest only when it is newer than the current latest Release. A tag push or Release create that loses a race to a concurrent run of the same publish keeps the winner's, if it is at this commit. This is the only place in the release flow that creates a tag; merging the settle PR is the approval. The default branch's changelog catches up in the next release candidate PR — nothing is back-merged. The consumer checks the repository out first (`fetch-depth: 0`, `persist-credentials: false`). Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `token` | yes |  | mega-gutenberg installation token from repository-scope `RELEASE_APP_CLIENT_ID` and `RELEASE_APP_PRIVATE_KEY`; gutenberg is the bypass actor on the `v*` tag ruleset, and a Release it creates fires `release: published` workflows. The one-reviewer `publish` environment gates only tagging, Release creation and artifact upload. |
| `version_file` | yes |  | File holding the version (VERSION, Cargo.toml, pyproject.toml, package.json); the same value as in release-candidate. |
| `version_pattern` | no | `plain` | How the version is stored in `version_file`: plain, toml or json. |
| `changelog_file` | no | `CHANGELOG.md` | Changelog the entry is written to (Keep-a-Changelog style, newest first). |
| `release_branch_prefix` | no | `release-v` | Release branch name prefix; the branch is `<prefix>X.Y.Z`. |
| `settle_source` | no | `pr` | Settlement source: pr verifies a merged settle PR; dispatch verifies a merged candidate PR and the current release-branch tip. |
| `release_branch` | no |  | Release branch that must equal <release_branch_prefix>X.Y.Z; for dispatch its tip must equal commit for a fresh publish, or contain commit when resuming an existing tag. |
| `commit` | yes |  | The commit to publish (full SHA); it must be the settle PR's merge commit for pr, or the candidate PR's merge commit for dispatch. |
| `pr_number` | yes |  | Number of the merged settle PR for pr, or the merged candidate PR for dispatch. |
| `pr_author` | no | `mega-gutenberg[bot]` | Login the settle or candidate PR must have been opened by — the app identity `release-settle` runs under. Stops a hand-made `chore/release-settle-*` branch from reaching the tag step. Empty disables the check only for pr. |
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
- `settle_source must be pr or dispatch, got`
- `candidate PR #$PR_NUMBER is not merged`
- `settle PR #$PR_NUMBER is not merged; publish only follows a merged settle PR`
- `candidate PR #$PR_NUMBER merge_commit_sha is`
- `settle PR #$PR_NUMBER merged as`
- `release_branch is required for dispatch settlement`
- `release_branch is`
- `candidate PR #$PR_NUMBER head ref is`
- `candidate PR #$PR_NUMBER base is`
- `candidate PR #$PR_NUMBER author is`
- `tag v$version already exists (at $(git rev-parse`
- `release branch`
- `head branch`
- `settle PR #$PR_NUMBER was opened by`
- `settle PR for v$version merged into`
- `settle PR body has no`
- `release branch drifted: settle PR settled $settled but the branch tip at merge was $parent. Re-run release-settle on the current tip.`
- `tag $tag already exists (at $(git rev-parse`
- `$FILE at $MERGE_SHA says $actual, expected $version`
- `changelog section for v$version at $MERGE_SHA disagrees with regenerated notes; let the settle refresh land first, then publish.`
- `could not push $TAG; the remote tag is at $(git rev-parse`
- `cannot read the latest Release to decide whether $TAG is the latest; re-run to resume`
- `could not create the Release for $TAG`
<!-- /generated -->

## Example

PR mode uses `settle_source: pr` (the default) and is triggered by the
settle PR's merge push to the release branch:

```yaml
- uses: megaeth-labs/.github/.github/actions/release-publish@main
  with:
    token: ${{ steps.app-token.outputs.token }}
    version_file: Cargo.toml
    version_pattern: toml
    changelog_file: CHANGELOG.md
    commit: ${{ steps.route.outputs.commit }}
    pr_number: ${{ steps.route.outputs.pr_number }}
```

For direct settlement, pass `settle_source: dispatch`, `release_branch`,
`commit` and the candidate PR's `pr_number`. The action verifies through the
GitHub API that the candidate is merged with `merge_commit_sha == commit`,
its head is `chore/release-candidate-<version>`, its base is the default
branch or `release_branch`, its author equals `pr_author`, and the current
release-branch tip equals `commit` for a fresh publish (no tag yet). When the
tag already exists at `commit`, the tip may equal it or be a descendant:
`git merge-base --is-ancestor "$MERGE_SHA" "$tip"` must succeed. This lets a
dispatch resume a tag without a Release after the branch has advanced, while
still refusing a fresh publish from a moved branch. The version comes from `version_file` at
`commit`; `release_branch` must equal `<release_branch_prefix><version>`.
This path skips the settle marker and first-parent checks and
repeats the entire state check inside the tag step immediately before tagging,
so branch drift during an environment approval is refused for a fresh publish.
Both refusal messages state the fresh-publish equality rule and the existing-tag
ancestry rule.

## Notes

- Creates the annotated tag once (refuses if it exists elsewhere; resumes or
  no-ops if it is already at this commit) at the merge commit
  in PR mode — refusing if the merge's first parent is not the settled SHA
  recorded in the PR, or the PR was not opened by `pr_author` — or at
  `commit` in dispatch mode; then publishes the GitHub Release with the
  changelog section as notes, marked latest only when it is newer than the
  current latest Release.
- If the tag exists at `commit` but its Release does not, both sources skip
  tagging and resume Release creation after their verification passes. Resume
  the settle-PR shape by re-running the push-triggered workflow; resume the
  direct shape by dispatching again with the same inputs. A tag elsewhere is
  always refused; a tag at `commit` with a Release already present is a no-op.
- The Release body is the changelog section extracted from the tagged tree,
  verbatim, with no injected date. With an empty `changelog_file`, notes are
  generated from non-merge commits since the previous release tag (or all
  commits for the first release), with an undated heading.
- Refuses a version that is not newer than every other `vX.Y.Z` tag (the
  rule `release-route` applies), in the guard and again right before the tag
  push; tags that are not `vX.Y.Z` are ignored.
- The tag push comes from the app token so `push: tags` and `release`
  workflows fire; the app must bypass the `v*` tag ruleset.
- This workflow must exist on the release branch (it does when the branch
  was cut from a default branch that has it).
