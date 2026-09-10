# Notify Lark

`uses: megaeth-labs/.github/.github/actions/notify-lark@main`

<!-- generated: description -->
Post a message to a Lark (Feishu) group through a custom-bot webhook. The default is a plain text message; `msg_type: post` sends rich text with a title, and `payload` sends any JSON you built yourself (interactive cards, mentions), untouched. If the bot has signature verification enabled, pass its signing `secret` and the request is signed with the documented timestamp + HMAC-SHA256 scheme. The webhook URL and secret go through the environment and are masked. A non-2xx response or a Lark error code fails the step unless `fail_on_error` is `false`; the response body is an output either way. Nothing is organisation-specific: the webhook is an input.
<!-- /generated -->

Standalone action; no family guide.

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `webhook_url` | yes |  | The custom bot's webhook URL (`https://open.larksuite.com/open-apis/bot/v2/hook/…` or the Feishu equivalent). |
| `message` | no |  | Message text. For `msg_type: post` each line becomes a paragraph. Ignored when `payload` is given. |
| `msg_type` | no | `text` | `text` or `post` (rich text with `title`). Ignored when `payload` is given. |
| `title` | no |  | Title for `msg_type: post`. |
| `payload` | no |  | A complete JSON request body to send as-is (any Lark message type). Overrides `message`, `msg_type` and `title`. |
| `secret` | no |  | The bot's signature-verification secret, if enabled. Adds `timestamp` and `sign` to the request. |
| `fail_on_error` | no | `true` | `true`: fail the step on a non-2xx response or a non-zero Lark `code`. |
| `timeout` | no | `15` | Seconds to wait for the webhook. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `code` | The Lark response `code` (0 means delivered), or the HTTP status when the body was not JSON. |
| `response` | The raw response body. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Send the message
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `webhook_url is required`
- `jq is not on this runner`
- `payload is not valid JSON`
- `message is required when payload is not given`
- `msg_type must be text or post (use payload for other types), got`
- `$msg`
<!-- /generated -->

## Example

Ping a group when a scheduled workflow fails:

```yaml
- if: failure()
  uses: megaeth-labs/.github/.github/actions/notify-lark@main
  with:
    webhook_url: ${{ secrets.LARK_CI_WEBHOOK }}
    message: |
      ${{ github.workflow }} failed on ${{ github.ref_name }}
      ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
```

Rich text with a title, signed because the bot has signature verification
on:

```yaml
- uses: megaeth-labs/.github/.github/actions/notify-lark@main
  with:
    webhook_url: ${{ secrets.LARK_CI_WEBHOOK }}
    secret: ${{ secrets.LARK_CI_WEBHOOK_SECRET }}
    msg_type: post
    title: Nightly E2E
    message: |
      14/14 legs green
      run ${{ github.run_id }}
```

Anything else Lark accepts (interactive cards, `@` mentions) goes through
`payload` as the complete JSON body.

## Notes

- The webhook URL and the secret are masked in the log; the message is
  not, it is your own text.
- A successful delivery is HTTP 2xx *and* Lark `code` 0; a Lark error such
  as `19001 param invalid` fails the step unless `fail_on_error: "false"`,
  and is reported in the `code` and `response` outputs either way.
- Signing follows the custom-bot documentation: `sign =
  base64(HMAC-SHA256(key = "<timestamp>\n<secret>", data = ""))`, with the
  runner's clock as the timestamp. Lark rejects signatures older than one
  hour.
- Needs `jq`, `curl` and `openssl` on the runner (all present on
  GitHub-hosted images).
