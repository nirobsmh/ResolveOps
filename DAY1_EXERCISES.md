# Day 1 exercises

Do these after running the provided baseline. They turn the starter into something you truly
own and can explain.

## Exercise 1 — Add a new ticket

Add a mock customer with an API authentication failure. Extend the rule-based triage and write
a test proving that the graph classifies it as `api_error` without proposing a financial action.

## Exercise 2 — Fail safely

Change the customer name to one that does not exist. The current workflow still continues.
Add a conditional edge after `investigate_customer` that routes missing customers to an
`escalate_unknown_customer` node.

## Exercise 3 — Make the policy guard configurable

Move the sensitive action names into a small policy configuration object and inject it into
`AgentNodes`. Write a test showing that `send_customer_email` can be allowed or blocked by
configuration.

## Exercise 4 — Compare deterministic and LLM results

Run the same ticket five times in `--llm` mode. Record whether issue types, priority, actions,
and confidence change. This is your first small evaluation and an excellent interview talking
point about nondeterminism.

## Questions to answer aloud

1. Which fields belong in graph state, and which should be runtime-only dependencies?
2. Why does `evidence` use a reducer while `root_cause` uses replacement semantics?
3. Which nodes are safe to retry? Which future action nodes will need idempotency keys?
4. What happens if an LLM proposes an unknown action?
5. How would a PostgreSQL checkpointer change deployment and recovery?

