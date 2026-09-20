"""Run one support ticket through the graph and print its live execution trace."""

import argparse
import json
import os
import uuid

from resolveops.agent.graph import build_graph
from resolveops.agent.reasoning import OpenAIReasoner, RuleBasedReasoner

DEFAULT_TICKET = (
    "ACME Inc says their invoice export has failed three times today. They also believe "
    "they were charged twice this month. They are on the Enterprise plan, and this is "
    "blocking their finance team before tomorrow. Please investigate and resolve it."
)


def _serialize(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump()  # type: ignore[union-attr]
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ResolveOps Day 1 graph")
    parser.add_argument("--ticket", default=DEFAULT_TICKET, help="Ticket body")
    parser.add_argument("--subject", default="Duplicate charge and invoice export failure")
    parser.add_argument("--llm", action="store_true", help="Use OpenAI structured output")
    args = parser.parse_args()

    if args.llm:
        if not os.getenv("OPENAI_API_KEY"):
            parser.error("OPENAI_API_KEY is required when --llm is enabled")
        reasoner = OpenAIReasoner(model=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    else:
        reasoner = RuleBasedReasoner()

    graph = build_graph(reasoner)
    thread_id = f"ticket-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "ticket_id": "ticket_1001",
        "subject": args.subject,
        "body": args.ticket,
        "evidence": [],
        "trace": [],
        "status": "received",
    }

    print("\nResolveOps execution\n")
    for update in graph.stream(initial_state, config=config, stream_mode="updates"):
        node_name, values = next(iter(update.items()))
        node_trace = values.get("trace", [])
        summary = node_trace[-1]["summary"] if node_trace else "completed"
        print(f"  [ok] {node_name}: {summary}")

    final_state = graph.get_state(config).values
    output = {
        "ticket_id": final_state["ticket_id"],
        "status": final_state["status"],
        "triage": final_state["triage"],
        "root_cause": final_state["root_cause"],
        "resolution_plan": final_state["resolution_plan"],
        "approval_required": final_state["approval_required"],
        "trace": final_state["trace"],
    }
    print("\nFinal state\n")
    print(json.dumps(_serialize(output), indent=2))


if __name__ == "__main__":
    main()
