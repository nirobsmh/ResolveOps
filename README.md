# ResolveOps — Day 1

ResolveOps is an agentic customer-operations workflow. This first milestone takes a support
ticket through triage, account investigation, policy lookup, root-cause analysis, resolution
planning, and a deterministic policy guard.

The default mode is intentionally deterministic and requires no API key. It gives us a stable
baseline for testing. An optional OpenAI mode demonstrates schema-constrained LLM output.

## Day 1 graph

```text
START
  -> triage_ticket
  -> investigate_customer
  -> retrieve_policy
  -> analyze_root_cause
  -> generate_resolution_plan
  -> policy_guard
  -> END
```

This is an explicit workflow, not an unconstrained autonomous loop. Each node has one job,
returns a partial state update, and adds an auditable trace event.

## Run it

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
resolveops
pytest -q
```

To use an OpenAI model for structured triage, diagnosis, and planning:

```bash
cp .env.example .env
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="gpt-5-mini"
resolveops --llm
```

You may replace `OPENAI_MODEL` with any model available to your account that supports
structured output.

## Read the code in this order

1. `src/resolveops/schemas.py` — Pydantic contracts at nondeterministic boundaries.
2. `src/resolveops/state.py` — JSON-safe checkpoint state and append reducers.
3. `src/resolveops/agent/graph.py` — nodes, edges, and the checkpointer.
4. `src/resolveops/agent/nodes.py` — business workflow logic.
5. `src/resolveops/agent/reasoning.py` — deterministic baseline vs. LLM provider.
6. `tests/test_graph.py` — behavioral guarantees.

## The architectural decisions you should be able to explain

### Why LangGraph?

The workflow has durable state, explicit steps, sensitive-action gates, and will later pause
for human approval. A plain model/tool loop hides these transitions and becomes harder to
resume, test, and audit.

### Why keep a deterministic reasoner?

It gives the system an offline baseline and makes orchestration tests reliable. Later evals can
compare an LLM against this baseline instead of treating every model response as correct.

### Why Pydantic outputs?

Natural-language output is not a safe API contract. Validated schemas constrain categories,
ranges, action names, and action parameters before downstream code uses them.

The validated objects are converted to plain dictionaries before entering persistent state.
This keeps checkpoints portable and avoids coupling stored workflow data to Python classes.

### Why is the policy guard ordinary code?

The model can propose an action, but it cannot authorize one. Deterministic application policy
decides whether financial or external side effects require approval.

### Why is evidence kept in state?

Conclusions and actions should remain traceable to customer data, payment records, logs, and
policy. This state will later support citations, evaluation, and a frontend agent trace.

## Day 1 definition of done

- The CLI completes the sample ticket end to end.
- It detects the duplicate payment and export timeout.
- It proposes a credit and a safe export retry.
- It marks the financial action as awaiting human approval.
- The full node trace is visible.
- All tests pass without an API key.

## What intentionally waits

- Day 2: PostgreSQL, pgvector, hybrid retrieval, reranking, and citations.
- Day 3: replace the in-process adapter with an MCP server.
- Day 4: robust tool execution, retries, and idempotency.
- Day 5: FastAPI, Next.js, streaming, LangGraph interrupt/resume approval.
- Day 6: evaluation dataset, safety metrics, tracing, latency, and cost.
- Day 7: deployment, README polish, demo video, and interview narrative.
