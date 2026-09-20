"""The persistent state passed between LangGraph nodes.

AgentState is a TypedDict of JSON-like values only. Pydantic validates at node
boundaries; dumping to dicts before writes keeps InMemorySaver (and later Postgres)
checkpoints portable. Annotated[..., add] fields accumulate across nodes; all
other keys use last-write-wins replacement semantics.
"""

from operator import add
from typing import Annotated

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """Shared workflow state for one ticket thread (keyed by checkpointer thread_id).

    total=False so nodes can return partial updates — LangGraph merges each
    node's return dict into the existing state rather than requiring a full rewrite.
    """

    ticket_id: str
    subject: str
    body: str
    # Checkpoints contain JSON-like values only. Pydantic validates at node boundaries.
    triage: dict[str, object]
    customer: dict[str, object]
    invoices: list[dict[str, object]]
    payments: list[dict[str, object]]
    logs: list[dict[str, object]]
    policy_passages: list[dict[str, str]]
    # Append reducer: investigate_customer and retrieve_policy both contribute facts.
    evidence: Annotated[list[dict[str, object]], add]
    root_cause: dict[str, object]
    resolution_plan: dict[str, object]
    approval_required: bool
    status: str
    # Append reducer: every node appends its TraceEvent so the full run is reconstructible.
    trace: Annotated[list[dict[str, object]], add]
