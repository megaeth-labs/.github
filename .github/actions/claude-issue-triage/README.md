# Claude Issue Triage

`uses: megaeth-labs/.github/.github/actions/claude-issue-triage@main`

<!-- generated: description -->
Run the centralized MegaETH Claude issue triage.
<!-- /generated -->

Family: [Claude CI](../CLAUDE-CI.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `claude_code_oauth_token` | yes |  | OAuth token for Claude Code. |
| `allowed_bots` | no | `mega-putin` | Bot accounts allowed to trigger Claude Code. |
| `extra_allowed_tools` | no |  | Additional Claude tools to append to the canonical allowedTools list. |
| `extra_prompt` | no |  | Additional prompt text appended after the canonical prompt. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
This action sets no outputs.
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. (unnamed run step)
1. `anthropics/claude-code-action`
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
Its shell steps report no errors of their own; failures come from the actions and tools it calls.
<!-- /generated -->

## Example

```yaml
on:
  issues:
    types: [opened]
jobs:
  triage:
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      issues: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: megaeth-labs/.github/.github/actions/claude-issue-triage@main
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

## Notes

- Triages newly opened issues with the centralised prompt plus the
  repository's own convention files; `extra_prompt` appends per-repository
  instructions.
