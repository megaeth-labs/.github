# Release Settle

`uses: megaeth-labs/.github/.github/actions/release-settle@main`

<!-- generated: description -->
Maintain a settle PR for a release candidate: verify `commit` is the tip of the release branch and carries the expected version, generate release notes from the commits since the previous tag, write them into the changelog under the candidate's undated `## vX.Y.Z` heading, and open or refresh a `chore/release-settle-vX.Y.Z` PR onto the release branch without rewriting its history. New commits on the release branch refresh this PR automatically; merging it is the settlement decision and release-publish then tags the merge commit once. Run as a step in a job the consumer owns; consumer checks the repository out first (`fetch-depth: 0`, `persist-credentials: false`). Needs `gh` and `python3` on the runner. Guide: .github/actions/RELEASE.md in megaeth-labs/.github.
<!-- /generated -->

Family: [Release pipeline](../RELEASE.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `token` | yes |  | mega-gutenberg GitHub App installation token. Pushes the settle branch and opens or refreshes the PR so that it triggers CI. |
| `version` | yes |  | Version being settled, X.Y.Z or vX.Y.Z. |
| `commit` | yes |  | Full SHA to settle. Must be the current tip of the release branch: the settlement is a statement about a specific commit, and the tip is the only commit a later merge can build on. |
| `version_file` | yes |  | File holding the version (VERSION, Cargo.toml, pyproject.toml, package.json); the same value as in release-candidate. |
| `version_pattern` | no | `plain` | How the version is stored in `version_file`: plain, toml or json. |
| `release_branch` | no |  | Defaults to `<release_branch_prefix>X.Y.Z`. |
| `release_branch_prefix` | no | `release-v` | Release branch name prefix; the branch is `<prefix>X.Y.Z`. |
| `changelog_file` | no | `CHANGELOG.md` | Changelog the entry is written to (Keep-a-Changelog style, newest first); empty disables changelog writes. |
| `pr_author` | no | `mega-gutenberg[bot]` | Author of the bot-maintained settle PR; PRs by other authors are superseded. |
| `pr_labels` | no |  | Comma-separated labels for the settle PR (for repos whose label gates apply to release branches too). |
| `git_user_name` | no | `mega-gutenberg[bot]` | Committer identity for the commits this action makes. |
| `git_user_email` | no | `348780249+mega-gutenberg[bot]@users.noreply.github.com` | Committer email for the commits this action makes. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `version` | The normalised version, X.Y.Z. |
| `pr_url` | URL of the settle PR. |
| `notes_file` | Path of the generated release-notes markdown. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Guard
1. Compare workflows with the default branch
1. Compute settlement state
1. Configure git identity *(only if `steps.state.outputs.state == 'needs-settle-pr'`)*
1. Generate release notes *(only if `steps.state.outputs.state == 'needs-settle-pr'`)*
1. Ensure the settle PR *(only if `steps.state.outputs.state == 'needs-settle-pr'`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `commit must be a full 40-hex SHA, got`
- `release branch $branch does not exist`
- `tag v$version already exists — this release is settled`
- `$COMMIT is not the tip of $branch (tip is $tip). Settle the tip, or move the branch first.`
- `$FILE at $COMMIT says $actual, expected $version`
- `$version is not newer than the latest tag ${latest:-<none>}`
- `${decision#*$`
- `settle PR not ensured; stopped while $stage`
- `$BRANCH moved to ${tip:-<deleted>} after this refresh of $COMMIT started (a settle PR merge or a new push); not touching the settle PR, the run for the new tip refreshes it`
- `could not merge $COMMIT into $head; close the settle PR so the next run recreates it`
- `$head was taken by a concurrent run but no open settle PR is visible yet; re-run this workflow`
- `settle PR not ensured after $attempt attempts of racing a concurrent run; re-run this workflow`
<!-- /generated -->

## Example

As used by `workflow-templates/release-settle.yml`. The refresh job needs no
environment; the publish job that tags and creates the Release declares
`environment: release`, whose required reviewers authorise the tag:

```yaml
- uses: megaeth-labs/.github/.github/actions/release-settle@main
  with:
    token: ${{ steps.app-token.outputs.token }}
    version: ${{ inputs.version }}
    commit: ${{ inputs.commit }}      # full SHA of the release-branch tip
    version_file: Cargo.toml
    version_pattern: toml
    changelog_file: CHANGELOG.md
```

The action itself never tags and never creates a Release: it only maintains
`chore/release-settle-vX.Y.Z`. Publishing is `release-publish`, called by the
template's publish job on a clean dispatch or on the settle PR's merge.

## Notes

- Before generating notes or ensuring the PR, `settle-state` compares the
  release-branch tip with the merged candidate PR, checks ancestry, and reads
  the open settle PR, tag and GitHub Release facts. If the branch is unchanged
  at the candidate merge with no open settle PR or tag, the action succeeds
  with step outputs `settled=false` and `state=clean`. The run summary says
  nothing was written: git identity configuration, notes generation and the
  entire ensure-PR step are skipped, so no settle branch, commit, PR creation,
  update or comment is made. Only `needs-settle-pr` reaches the existing PR flow,
  including its deliberate `--allow-empty` commit when a fresh branch records
  settlement.
- Guards, in order: `commit` is a full SHA; the release branch exists; the
  tag does not; `commit` is the branch tip; the version file at `commit`
  says the version; the version is newer than the latest `v*` tag. Then a
  warning if `commit` lacks a workflow the default branch has (a `release`
  event runs `on-release.yml` from the tag's tree).
- This action never tags and never creates a Release: it maintains
  `chore/release-settle-vX.Y.Z` only. `release-publish` does the tagging, run
  by the template's publish job on a clean dispatch (where the `release`
  environment's required reviewers are the gate) or on the settle PR's merge.
- `pr`: pushes `chore/release-settle-vX.Y.Z` and opens the settle PR,
  titled `chore(release): settle vX.Y.Z — merging publishes the release`.
  Its body opens with an `[!IMPORTANT]` alert saying that merging it settles
  the release, followed by the `<!-- release-settle: vX.Y.Z <sha> -->`
  marker that `release-route` and `release-publish` read. A new tip on the
  release branch merges into the same PR and moves the marker; a re-run
  with nothing new changes nothing. Only a PR that is closed, merged or not
  authored by `pr_author` is replaced by a fresh branch. Nothing is
  force-pushed, and the branch is pushed only after the merge and the
  changelog commit both succeed. A run that loses a race with a concurrent
  run refreshes the PR that run opened.
- The full flow, installation and recovery: [RELEASE.md](../RELEASE.md).
