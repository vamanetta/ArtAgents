# OpenRouter Backend

ArtAgents uses LLMs for arrangement, editor review, scene description, triage,
quote scouting, and human-notes translation. The default backend is Anthropic's
Claude API. An OpenRouter fallback allows any model available on
[openrouter.ai](https://openrouter.ai) to be used instead — GPT, Claude, Llama,
Mistral, and others — via a single API key.

## Key Detection

`build_claude_client()` in `artagents/utilities/llm_clients.py` auto-detects
which backend to use at runtime:

1. If `ANTHROPIC_API_KEY` is set (env var or `.env` file), use Anthropic.
2. If `ANTHROPIC_API_KEY` is absent and `OPENROUTER_API_KEY` is set, use
   OpenRouter.
3. If neither is set, raise an error.

No code changes or flags are needed at call sites. Every module that calls
`build_claude_client()` transparently gets whichever backend is available.

## Setup

```bash
# Option A: Anthropic direct
export ANTHROPIC_API_KEY="sk-ant-..."

# Option B: OpenRouter (any model)
export OPENROUTER_API_KEY="sk-or-v1-..."
```

Or create a sourceable file:

```bash
#!/bin/bash
export OPENROUTER_API_KEY="sk-or-v1-your-key-here"
echo "OPENROUTER_API_KEY has been set"
```

```bash
source set_OPENROUTER.bat
```

Keys can also be placed in `.env` files and passed via `--env-file` flags on
individual executor commands.

## How It Works

The OpenRouter client uses the `openai` Python SDK (already in
`requirements.txt`) pointed at `https://openrouter.ai/api/v1`. It translates
between calling conventions:

- Anthropic tool-use (`tools` with `input_schema`) becomes OpenAI function
  calling (`tools` with `parameters`)
- Anthropic image blocks (`source.type: "base64"` / `"url"`) become OpenAI
  vision format (`image_url.url`)
- System prompts move from the Anthropic `system` parameter to an OpenAI
  system message

The `ClaudeClient` protocol is unchanged. Both backends implement
`complete_json()` which returns structured JSON via forced tool use.

## Model Selection

Each executor specifies its model in its own code (typically
`DEFAULT_MODEL`). The model string is passed through to whichever backend is
active. When using OpenRouter, use OpenRouter model IDs:

- `anthropic/claude-sonnet-4-20250514`
- `openai/gpt-4o`
- `meta-llama/llama-3.1-405b-instruct`

When using Anthropic directly, use Anthropic model IDs:

- `claude-sonnet-4-20250514`

## Debug Logging

Both backends write request/response pairs to `_llm_debug/` inside the run
directory. Each call produces `<stage>.<seq>.request.json` and
`<stage>.<seq>.response.json` with the full payload, provider name, model,
and status. A `_llm_debug/log.jsonl` file accumulates one-line summaries.
