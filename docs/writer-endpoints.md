# Writer endpoints

The writer types text, proposes URLs, and reads the screen whenever the classifier stops. By
default it is Claude on `api.anthropic.com`. These variables change the model or send it to
another endpoint.

| variable | required | purpose |
|---|---|---|
| `CLICKER_WRITER_BASE_URL` | no | send the writer to another endpoint; unset means `api.anthropic.com` |
| `CLICKER_WRITER_API_KEY` | no | the key for `CLICKER_WRITER_BASE_URL`, if it checks one |
| `AI_GATEWAY_API_KEY` | no | the key for [Vercel's AI Gateway](#vercel-ai-gateway), when `CLICKER_WRITER_BASE_URL` names it; `VERCEL_OIDC_TOKEN` also serves |
| `CLICKER_WRITER_API` | no | what that endpoint speaks: `anthropic` (the default) or `openai` |
| `CLICKER_WRITER_MODEL` | no | types text and proposes URLs; defaults to `claude-haiku-4-5` (`anthropic/claude-haiku-4.5` on Vercel's AI Gateway) |
| `CLICKER_ANSWER_MODEL` | no | reads the screen whenever the classifier stops; defaults to `claude-sonnet-5` (`anthropic/claude-sonnet-5` on Vercel's AI Gateway) |
| `CLICKER_WRITER_VISION` | no | `false` for an answer model that reads text only; defaults to `true` |
| `CLICKER_WRITER_REASONING` | no | the reasoning effort the writer's calls ask an OpenAI-API model for, such as `none`; unset leaves it to the model |
| `CLICKER_ANSWER_REASONING` | no | the same for the answer model, such as `low` |

## Other models

Point `CLICKER_WRITER_BASE_URL` at any endpoint that speaks the Anthropic
Messages API or, with `CLICKER_WRITER_API=openai`, OpenAI's Chat Completions API: LM Studio,
Ollama, vLLM, a LiteLLM proxy, DeepSeek. Name the models it serves. The full request URL works as
well as the root; for the OpenAI API keep the `/v1`. Such an endpoint may ignore structured-output
parameters, so the schema is also spelled out in the prompt, and code fences or a sentence around
the JSON are tolerated. On the OpenAI API a `json_schema` response format is asked for first, then
`json_object`, then none, stepping down only when the endpoint refuses one. Thinking is turned off,
since a model that thinks by default spends the writer's small token budgets on it and returns no
text. The answer model reads a screenshot; for a model that reads text only, set
`CLICKER_WRITER_VISION=false` and it gets the screen's text alone. A reply that cannot be read
refuses the step it was for, and the run goes on.

Keys never cross over: `CLICKER_WRITER_API_KEY` goes only to `CLICKER_WRITER_BASE_URL`,
`AI_GATEWAY_API_KEY` and `VERCEL_OIDC_TOKEN` only to Vercel's AI Gateway, and `ANTHROPIC_API_KEY` and
`OPENAI_API_KEY` never go to either. On the Anthropic API the endpoint's key is sent in both the
`x-api-key` and `Authorization` headers, since proxies differ. Leave it empty for an endpoint that
checks no key.

## Vercel AI Gateway

[Vercel's AI Gateway](https://vercel.com/docs/ai-gateway) speaks both APIs, so the writer runs
through it with one URL and Vercel's own key. Its spend and traces then show in the Vercel
dashboard, and any model it serves can write or answer. The TypeSafe classifier, which makes every
other decision, still talks to TypeSafe.

```
CLICKER_WRITER_BASE_URL=https://ai-gateway.vercel.sh
AI_GATEWAY_API_KEY=vck_...
```

When the URL names the gateway, `AI_GATEWAY_API_KEY` is its key, or `VERCEL_OIDC_TOKEN` from
`vercel env pull`, which lasts 12 hours; `CLICKER_WRITER_API_KEY` wins over both. Without any of
them the run stops before it starts, since the gateway checks every request. The gateway names each
model by its maker, with dots in the version, so the defaults there are `anthropic/claude-haiku-4.5`
and `anthropic/claude-sonnet-5`, the same two models. Any other model it lists at
`https://ai-gateway.vercel.sh/v1/models` works too:

```
CLICKER_WRITER_MODEL=google/gemini-3.5-flash-lite
CLICKER_ANSWER_MODEL=openai/gpt-5.4-mini
```

The Anthropic API is the default and needs nothing more. For the OpenAI one, set
`CLICKER_WRITER_API=openai` and keep the `/v1`: `https://ai-gateway.vercel.sh/v1`. With Claude Code's
own setup for the gateway (`ANTHROPIC_BASE_URL=https://ai-gateway.vercel.sh` and the key in
`ANTHROPIC_AUTH_TOKEN`) the writer uses the gateway's model names as well.

## Examples

```
# LM Studio, either of its two APIs
CLICKER_WRITER_BASE_URL=http://localhost:1234
CLICKER_WRITER_MODEL=qwen3.8-flash-next
CLICKER_ANSWER_MODEL=qwen3.8-flash-next

# any OpenAI-compatible server
CLICKER_WRITER_API=openai
CLICKER_WRITER_BASE_URL=https://api.deepseek.com/v1
CLICKER_WRITER_API_KEY=sk-...
CLICKER_WRITER_MODEL=deepseek-v4.1-flash
CLICKER_ANSWER_MODEL=deepseek-v4.1-flash
CLICKER_WRITER_VISION=false
```
