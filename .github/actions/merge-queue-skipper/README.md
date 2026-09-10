# Merge Queue Skipper

`uses: megaeth-labs/.github/.github/actions/merge-queue-skipper@main`

<!-- generated: description -->
Decide whether a merge-queue run may skip checks that already passed on the pull request. GitHub always re-runs required checks on the temporary merge branch; this outputs `skip-check: true` only when that branch's tree is provably the one the PR's own checks covered: the entry was enqueued at the head of the target branch, the PR branch still contains that commit, and the PR branch and the queue branch have no diff. Any other situation — not a merge-queue ref, a queue entry behind another, a PR updated after enqueueing — yields `false`. The caller gates its expensive jobs on the output. Needs the repository history: the action checks it out itself (`fetch-depth: 0`) unless `checkout: false`, in which case the caller must already have a full checkout with `origin` remote.
<!-- /generated -->

Standalone action; no family guide.

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `token` | no | `${{ github.token }}` | Token for `gh pr view` (reads the PR's head branch). The job token is enough. |
| `checkout` | no | `true` | `true`: check the repository out with full history first. `false` if the job already did. |
| `target_branch` | no |  | Override the target branch parsed from the merge-queue ref (rarely needed). |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `skip-check` | `true` when the queue branch equals the already-checked PR tree, else `false`. |
| `pr_number` | The PR number parsed from the merge-queue ref (empty outside a queue). |
| `target_branch` | The target branch parsed from the merge-queue ref (empty outside a queue). |
| `commit` | The target-branch commit the queue entry was built on (empty outside a queue). |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Check out the repository with history — `actions/checkout` *(only if `inputs.checkout == 'true'`)*
1. Parse the merge-queue ref
1. Compare the queue branch with the PR branch *(only if `steps.parse.outputs.in_queue == 'true'`)*
1. Result
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
Its shell steps report no errors of their own; failures come from the actions and tools it calls.
<!-- /generated -->

## Example

Gate the expensive jobs of a workflow that also runs on `merge_group`:

```yaml
on:
  pull_request:
  merge_group:

jobs:
  skipper:
    runs-on: ubuntu-latest
    outputs:
      skip: ${{ steps.check.outputs.skip-check }}
    steps:
      - id: check
        uses: megaeth-labs/.github/.github/actions/merge-queue-skipper@main

  test:
    needs: skipper
    if: needs.skipper.outputs.skip != 'true'
    runs-on: ubuntu-latest
    steps:
      - run: cargo test --workspace

  # Required checks must still report; a skipped job does not, so give the
  # branch rule a job that always runs and passes when the work was skipped.
  test-status:
    needs: [skipper, test]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - run: |
          [[ "${{ needs.skipper.outputs.skip }}" == "true" || "${{ needs.test.result }}" == "success" ]]
```

## Notes

- `true` needs all three conditions: the entry was enqueued on the current
  head of the target branch, the PR branch still contains that commit, and
  the PR branch tree equals the queue branch tree. In that state the PR's
  own checks ran on exactly this tree. Everything else, including any run
  outside a merge queue, is `false`.
- It checks the repository out itself with full history because
  `--contains` and the diff need it; pass `checkout: "false"` if the job
  already did (with `fetch-depth: 0`).
- Reads the PR's head branch through `gh pr view` with `token` (the job
  token is enough).
- This is the hardened copy of mega-reth's local `queue_skipper`: pinned
  action SHAs, values through `env:`, exact-match `grep`.
