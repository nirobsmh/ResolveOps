"""Validated contracts shared by agent nodes and model providers."""

from typing import Literal

from pydantic import BaseModel, Field

IssueType = Literal[
    "billing",
    "invoice_export",
    "account_access",
    "api_error",
    "unknown",
]


class TicketInput(BaseModel):
    ticket_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


class TriageResult(BaseModel):
    customer_name: str | None = None
    issue_types: list[IssueType] = Field(min_length=1)
    priority: Literal["low", "medium", "high", "urgent"]
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class Evidence(BaseModel):
    source: Literal["customer", "invoice", "payment", "log", "policy"]
    reference: str
    fact: str


class RootCause(BaseModel):
    findings: list[str]
    root_causes: list[str]
    confidence: float = Field(ge=0, le=1)


class ProposedAction(BaseModel):
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
    customer_summary: str
    internal_summary: str
    actions: list[ProposedAction]


class TraceEvent(BaseModel):
    stage: str
    status: Literal["completed", "pending", "failed"] = "completed"
    summary: str
    details: dict[str, object] = Field(default_factory=dict)
