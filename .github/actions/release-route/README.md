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
| `action` | Next action: cut, refresh, publish or skip; versioned settle dispatch returns publish, refresh or skip. |
| `reason` | Why this action was selected. |
| `settle_source` | Publication source: dispatch for a versioned settle dispatch routed to publish; empty otherwise. |
| `version` | Normalized release version, when routing one push. |
| `release_branch` | Release branch for the pushed version. |
| `commit` | Pushed commit for cut, refresh or publish. |
| `pr_number` | Merged release PR number, or candidate PR number for a versioned settle dispatch, when provided. |
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

For `kind: settle` on `workflow_dispatch` with a `version`, `action` is
`publish`, `refresh` or `skip`: publish or resume publication, refresh the
settle PR, or take no action, respectively. `reason` explains the decision.
`settle_source` is `dispatch` when the decision is `publish` and empty
otherwise; `pr_number` is the selected merged candidate PR's `.number`,
passed as `candidate_pr_number` to `route()` and written to `GITHUB_OUTPUT`
by the decision output loop.
The action passes the dispatch context to `route()` unchanged and exposes
its decision without remapping it. Candidate pushes may still return `cut`.

For a versioned settle dispatch, each enumerated release branch includes
`candidate_merge_sha` from the merged candidate PR with head
`chore/release-candidate-<version>` (no leading `v`) targeting the default
branch or that release branch, `candidate_is_ancestor` from a Git ancestry
check against its tip, `open_settle_pr` from the open settle PR lookup, and
`published_tag_sha` from the peeled release tag (or the lightweight tag).
All four keys are always present: missing SHAs and ancestry without a candidate
are empty strings, and no open settle PR is `false`. A selected branch without a
candidate merge fails with `missing settlement facts: candidate_merge_sha`;
it does not route to a successful skip. Dispatches without a
version leave these facts empty or false.

Each dispatch branch also includes `release_exists`, queried with
`gh release view v<version>` when its tag exists and otherwise `false`.
Together with the tag facts, this lets an already published version route
to `skip` instead of `publish`. The tag must point at the candidate merge:
a tag at a settle-PR merge is `blocked` by versioned dispatch, whether or not
its Release exists. Recover an interrupted settle-PR publication by re-running
its original push-triggered run, not by versioned dispatch.

For an ordinary push after the candidate lands, routing returns `refresh`
without comparing changelog state. The settle action then compares the
section and may find `clean`, write nothing and create no PR. Publish that
branch with a versioned dispatch. Dispatch routing also does not compare
the section: it assumes a match, and `release-publish` refuses stale notes
before tagging. Use a blank-version dispatch to refresh stale notes first.
The versioned dispatch route does not check version ordering; the publish
guard still refuses versions not newer than every other `vX.Y.Z` tag.

The workflow accepts only `version` on dispatch. A blank version refreshes all
eligible branches and never publishes. The `version`, `release_branch` and
`commit` outputs also describe a selected versioned dispatch; a resume uses
the existing tag's peeled commit rather than a branch tip that has advanced.

A push to a `release_branch_prefix` branch whose suffix is not `X.Y.Z` (for
example `release-vnext`) routes to `skip` with a reason naming the branch; a
manual dispatch leaves such branches out of `targets`. Input the route cannot
read fails the step with a `Release route` error annotation.
