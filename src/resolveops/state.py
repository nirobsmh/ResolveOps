"""The persistent state passed between LangGraph nodes."""

from operator import add
from typing import Annotated

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
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
    evidence: Annotated[list[dict[str, object]], add]
    root_cause: dict[str, object]
    resolution_plan: dict[str, object]
    approval_required: bool
    status: str
    trace: Annotated[list[dict[str, object]], add]
