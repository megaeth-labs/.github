# Claude Interactive

`uses: megaeth-labs/.github/.github/actions/claude-interactive@main`

<!-- generated: description -->
Run the interactive @claude handler with centralized MegaETH permissions.
<!-- /generated -->

Family: [Claude CI](../CLAUDE-CI.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `claude_code_oauth_token` | yes |  | OAuth token for Claude Code. |
| `allowed_bots` | no | `mega-putin` | Bot accounts allowed to trigger Claude Code. |
| `extra_allowed_tools` | no |  | Additional Claude tools to append to the canonical allowedTools list. |
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
jobs:
  interactive:
    if: contains(github.event.comment.body, '@claude')   # plus the review/issue event variants
    runs-on: ubuntu-24.04
    timeout-minutes: 45
    permissions:
      contents: write
      pull-requests: write
      issues: write
      id-token: write
      actions: read
    steps:
      - uses: actions/checkout@v4
      - uses: megaeth-labs/.github/.github/actions/claude-interactive@main
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          extra_allowed_tools: "Bash(just:*),Bash(npm:*)"
```

## Notes

- Handles `@claude` mentions in issue comments, PR review comments and
  reviews with the organisation's permission set; there is no
  `extra_prompt`, since `@claude` conversations are native.
- `allowed_bots` names the bot accounts whose mentions may trigger it.
