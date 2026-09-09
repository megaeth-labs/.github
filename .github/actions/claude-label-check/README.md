# Claude Label Check

`uses: megaeth-labs/.github/.github/actions/claude-label-check@main`

<!-- generated: description -->
Run the centralized MegaETH Claude pull request label check.
<!-- /generated -->

Family: [Claude CI](../CLAUDE-CI.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `claude_code_oauth_token` | yes |  | OAuth token for Claude Code. |
| `allowed_bots` | no | `mega-putin` | Bot accounts allowed to trigger Claude Code. |
| `extra_allowed_tools` | no |  | Additional Claude tools to append to the canonical allowedTools list. |
| `self_authored_logins` | no | `mega-maxwell[bot]` | Comma-separated logins whose pull requests are skipped rather than label-checked: the CI app's own PRs (release candidates, settle PRs, dependency bumps). claude-code-action refuses bot-initiated events, so without this the check fails instead of saying it does not apply. |
| `extra_prompt` | no |  | Additional prompt text appended after the canonical prompt. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
This action sets no outputs.
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. (unnamed run step)
1. (unnamed run step) *(only if `steps.gate.outputs.skip != 'true'`)*
1. `anthropics/claude-code-action` *(only if `steps.gate.outputs.skip != 'true'`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
Its shell steps report no errors of their own; failures come from the actions and tools it calls.
<!-- /generated -->

## Example

```yaml
jobs:
  label-check:
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      pull-requests: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: megaeth-labs/.github/.github/actions/claude-label-check@main
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          extra_prompt: |
            This repository's label conventions are in CONTRIBUTING.md.
```

## Notes

- PRs opened by any login in `self_authored_logins` (the CI app by
  default) are skipped rather than checked: the app's release and
  dependency PRs carry the labels the settle/candidate actions were given.
- The prompt reads the repository's own convention files first
  (`REVIEW.md`, `CLAUDE.md`, `AGENTS.md`, …); `extra_prompt` is for small
  deltas only.
