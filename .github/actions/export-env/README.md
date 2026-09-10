# Export Env

`uses: megaeth-labs/.github/.github/actions/export-env@main`

<!-- generated: description -->
Load a dotenv file into the job: every `KEY=value` line (an `export ` prefix, surrounding quotes, blank lines and `#` comments are handled) becomes an environment variable for the following steps, or an entry in the `json` output, or both. Only the keys are logged, never the values — a `.env` that carries a credential stays out of the log — and `mask: true` also registers each value with `::add-mask::`. `prefix` limits the load to one namespace and `strip_prefix` drops it from the exported names.
<!-- /generated -->

Standalone action; no family guide.

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `file` | yes |  | Path of the dotenv file, relative to the workspace. |
| `target` | no | `env` | `env` (the next steps' environment), `json` (only the `json` output), or `both`. |
| `prefix` | no |  | Only load keys that start with this prefix. |
| `strip_prefix` | no | `false` | `true`: remove `prefix` from the exported names. |
| `override` | no | `true` | `false`: keep a variable that is already set in the job environment. |
| `mask` | no | `false` | `true`: `::add-mask::` every loaded value of 8 characters or more, so it is redacted wherever it later shows up in the log. Shorter values are never masked (masking `1` or `true` would redact every log line containing them). |
| `required` | no | `true` | `true`: fail if the file does not exist; `false`: exit quietly with nothing loaded. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `keys` | Comma-separated list of the names that were exported. |
| `count` | How many variables were exported. |
| `json` | The loaded pairs as a JSON object, for `fromJSON(steps.<id>.outputs.json).<NAME>` in later steps or jobs. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Load the dotenv file
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `target must be env, json or both, got`
- `jq is not on this runner`
- `dotenv file not found: $FILE`
<!-- /generated -->

## Example

```yaml
- uses: megaeth-labs/.github/.github/actions/export-env@main
  with:
    file: ci/topologies/cluster.env

- run: echo "$OP_NODE_TAG"        # every KEY in the file is now set
```

Load one namespace as data instead of environment, and read it back with
`fromJSON`:

```yaml
- uses: megaeth-labs/.github/.github/actions/export-env@main
  id: cfg
  with:
    file: deploy.env
    target: json
    prefix: DEPLOY_
    strip_prefix: "true"

- run: echo "${{ fromJSON(steps.cfg.outputs.json).REGION }}"
```

## Notes

- Values are never printed; the log lists the keys only. `mask: "true"`
  additionally registers values of 8+ characters with the runner so they
  are redacted wherever they appear later (shorter values are left alone —
  masking `1` or `true` would redact every log line that contains them).
- Parsing is dotenv-style: `export KEY=value` lines, blank lines, `#`
  comments, and one pair of surrounding single or double quotes are
  handled; no variable expansion, no multi-line values.
- `override: "false"` keeps a variable the job already has, so a workflow
  can let its own `env:` win over the file.
- With `target: json` nothing enters the environment; the `json` output
  holds every loaded pair (the values included, so treat it like the file).
