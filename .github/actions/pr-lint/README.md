# PR Lint

`uses: megaeth-labs/.github/.github/actions/pr-lint@main`

<!-- generated: description -->
Lint a pull request. Currently validates that the PR title follows Conventional Commits, posting a sticky comment on failure and removing it once fixed; further PR-level lint steps can be added here over time. Run as a step inside a job the consumer names, so the resulting status-check context is that job name.
<!-- /generated -->

Standalone action; no family guide.

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `types` | no | `feat
fix
chore
test
bench
perf
refactor
docs
ci
revert
deps
` | Newline-separated list of allowed Conventional Commit types. Defaults to the MegaETH org convention. |
| `github_token` | no | `${{ github.token }}` | Token used by the semantic-PR check and the sticky comment. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
This action sets no outputs.
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Skip for merge queue *(only if `github.event_name == 'merge_group'`)*
1. Check title — `amannn/action-semantic-pull-request` *(only if `github.event_name == 'pull_request'`)*
1. Add PR Comment for Invalid Title — `marocchino/sticky-pull-request-comment` *(only if `github.event_name == 'pull_request' && steps.lint_pr_title.outcome == 'failure'`)*
1. Remove Comment for Valid Title — `marocchino/sticky-pull-request-comment` *(only if `github.event_name == 'pull_request' && steps.lint_pr_title.outcome == 'success'`)*
1. Fail if title invalid *(only if `github.event_name == 'pull_request' && steps.lint_pr_title.outcome == 'failure'`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
Its shell steps report no errors of their own; failures come from the actions and tools it calls.
<!-- /generated -->

## Example

```yaml
name: PR Lint
on:
  pull_request:
    types: [opened, reopened, edited, synchronize]
  merge_group:
jobs:
  conventional-title:
    name: Validate PR title is Conventional Commit
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: megaeth-labs/.github/.github/actions/pr-lint@main
```

## Notes

- Run it as a step inside a job the consumer names: the status-check
  context is the job name, so a branch ruleset that requires an exact check
  name is satisfied by naming the job accordingly.
- On a bad title it posts a sticky comment and fails; once the title is
  fixed the comment is removed. Merge-queue events are skipped.
- `types` overrides the allowed Conventional Commit types; the default is
  the organisation's convention.
