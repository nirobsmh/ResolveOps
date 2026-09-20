"""Validated contracts shared by agent nodes and model providers.

Pydantic models sit at nondeterministic boundaries (LLM output, node I/O).
Validated objects are dumped to plain dicts before they enter LangGraph state so
checkpoints stay JSON-portable and decoupled from Python class identity.
"""

from typing import Literal

from pydantic import BaseModel, Field

# Closed set of categories — structured output cannot invent arbitrary issue labels.
IssueType = Literal[
    "billing",
    "invoice_export",
    "account_access",
    "api_error",
    "unknown",
]


class TicketInput(BaseModel):
    """Raw support ticket payload accepted at the workflow entrypoint."""

    ticket_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


class TriageResult(BaseModel):
    """First-pass classification: who is affected, what kind of issue, how urgent.

    Produced by a Reasoner (rule-based or LLM). Downstream investigation uses
    customer_name to look up account data; issue_types drive diagnosis and planning.
    """

    customer_name: str | None = None
    issue_types: list[IssueType] = Field(min_length=1)
    priority: Literal["low", "medium", "high", "urgent"]
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class Evidence(BaseModel):
    """One citeable fact gathered during investigation or policy retrieval.

    Kept in state with an append reducer so later nodes can cite sources without
    overwriting earlier findings. Feeds root-cause analysis and future evals.
    """

    source: Literal["customer", "invoice", "payment", "log", "policy"]
    reference: str
    fact: str


class RootCause(BaseModel):
    """Diagnosis derived from triage + accumulated evidence.

    findings are observations; root_causes are the inferred failure modes that
    the resolution planner turns into concrete actions.
    """

    findings: list[str]
    root_causes: list[str]
    confidence: float = Field(ge=0, le=1)


class ProposedAction(BaseModel):
    """A single side-effect the agent wants to take — not yet authorized.

    action is a closed Literal so unknown tool names fail validation instead of
    reaching execution. risk and the action name feed the deterministic policy guard.
    """

    action: Literal[
        "issue_account_credit",
        "retry_invoice_export",
        "update_ticket",
        "send_customer_email",
        "escalate_to_human",
    ]
    reason: str
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    risk: Literal["low", "medium", "high"]


class ResolutionPlan(BaseModel):
    """Customer-facing and internal summaries plus the proposed action list."""

    customer_summary: str
    internal_summary: str
    actions: list[ProposedAction]


class TraceEvent(BaseModel):
    """Auditable breadcrumb emitted by each graph node for the CLI and future UI."""

    stage: str
    status: Literal["completed", "pending", "failed"] = "completed"
    summary: str
    details: dict[str, object] = Field(default_factory=dict)
