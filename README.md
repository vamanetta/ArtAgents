# ArtAgents

ArtAgents is a harness toolkit for agents and humans to make art.

## How it works

Give this to your agents to get started:

<div align="center">

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇━━━━━━━━━━━━━━◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ·                                                                        · ┃
┃   ╳ ╳ ╳ ╳ ╳────────────────────────────────────────────────────╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳            ═══  A R T A G E N T S  ═══             ╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳────────────────────────────────────────────────────╳ ╳ ╳ ╳ ╳   ┃
┃                                                                            ┃
┃                             ◇  What This Is  ◇                             ┃
┃            a harness toolkit for agents and humans to make art             ┃
┃                                                                            ┃
┃                EXECUTORS      perform one piece of work                    ┃
┃                ORCHESTRATORS  combine executors together                   ┃
┃                ELEMENTS       reusable pieces used by both                 ┃
◇                                                                            ◇
┃                           ◇  Getting Started  ◇                            ┃
┃          git clone https://github.com/peteromallet/ArtAgents.git           ┃
┃        python3 -m artagents [executors|orchestrators|elements] list        ┃
┃    python3 -m artagents [executors|orchestrators|elements] inspect <id>    ┃
┃     python3 -m artagents [executors|orchestrators] run <id> -- <args>      ┃
◇                                                                            ◇
┃                          ◇  Make Something New  ◇                          ┃
┃            copy docs/templates/{executor,orchestrator,element}/            ┃
┃                        read docs/creating-tools.md                         ┃
┃                                                                            ┃
┃   ╳ ╳ ╳ ╳ ╳────────────────────────────────────────────────────╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳          ask the maker what they must do           ╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳         docs/ideas.md has a thought or two         ╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳          runs/ is where the outputs stay           ╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳          just begin, you'll find your way          ╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳────────────────────────────────────────────────────╳ ╳ ╳ ╳ ╳   ┃
┃ ·                                                                        · ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇━━━━━━━━━━━━━━◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

</div>

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
cd remotion && npm install && cd ..
python3 -m artagents doctor
```

## LLM Backend

ArtAgents requires an LLM for arrangement, review, and description stages.
Set one of these keys before running:

```bash
# Anthropic (primary)
export ANTHROPIC_API_KEY="sk-ant-..."

# OpenRouter (fallback — any model via openrouter.ai)
export OPENROUTER_API_KEY="sk-or-v1-..."
```

When both keys are present, Anthropic is used. When only `OPENROUTER_API_KEY`
is set, all LLM calls route through OpenRouter automatically. No code changes
needed. See [`docs/openrouter.md`](docs/openrouter.md) for details.

## Quick Start

```bash
# Source-backed video
python3 -m artagents --video source.mp4 --brief brief.txt --out runs/example --render

# Pure-generative video from a written brief
python3 -m artagents --brief examples/briefs/cinematic.txt --out runs/cinematic --render --target-duration 15
```

## Agent Control Loop

After a run completes, an AI agent can inspect, edit, and re-render without
human intervention. See [`docs/agent-loop.md`](docs/agent-loop.md) for the
full protocol.

```bash
python3 -m artagents inspect-run runs/example       # read run state as JSON
python3 -m artagents revise runs/example --edits edits.json   # apply edits
python3 -m artagents rerender runs/example           # rebuild from cut onward
python3 -m artagents review runs/example             # generate HTML review
```

## Documentation

| Document | Purpose |
| --- | --- |
| [`docs/architecture.md`](docs/architecture.md) | Module map, pack system, structure enforcement |
| [`docs/creating-tools.md`](docs/creating-tools.md) | When to create an executor, orchestrator, or element |
| [`docs/agent-loop.md`](docs/agent-loop.md) | Agent inspect-edit-render protocol |
| [`docs/openrouter.md`](docs/openrouter.md) | Multi-backend LLM support |
| [`docs/threads.md`](docs/threads.md) | Local run continuity layer |
| [`docs/ideas.md`](docs/ideas.md) | Prompts for when the maker is unsure |

## Tests

```bash
source venv/bin/activate
python3 -m pytest tests/ -q
```

## License

Open Source Native License (OSNL) v0.2 — see [`LICENSE`](LICENSE).
