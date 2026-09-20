"""Reasoning providers: deterministic for tests, structured LLM output for demos."""

import json
import re
from typing import Protocol

from resolveops.schemas import (
    Evidence,
    ProposedAction,
    ResolutionPlan,
    RootCause,
    TriageResult,
)


class Reasoner(Protocol):
    def triage(self, subject: str, body: str) -> TriageResult: ...

    def analyze(self, triage: TriageResult, evidence: list[Evidence]) -> RootCause: ...

    def plan(self, triage: TriageResult, root_cause: RootCause) -> ResolutionPlan: ...


class RuleBasedReasoner:
    """Repeatable baseline. Useful for unit tests and for measuring LLM lift later."""

    def triage(self, subject: str, body: str) -> TriageResult:
        text = f"{subject}\n{body}".lower()
        issue_types = []
        if any(word in text for word in ("charged", "charge", "payment", "refund", "duplicate")):
            issue_types.append("billing")
        if "invoice" in text and any(word in text for word in ("export", "download", "failed")):
            issue_types.append("invoice_export")
        if not issue_types:
            issue_types.append("unknown")

        match = re.search(r"\b([A-Z][A-Za-z0-9&-]*(?:\s+(?:Inc\.?|LLC|Ltd\.?|Corp\.?)))\b", body)
        customer_name = match.group(1) if match else None
        urgent_words = ("urgent", "blocking", "before tomorrow", "production")
        priority = "urgent" if any(word in text for word in urgent_words) else "medium"

        return TriageResult(
            customer_name=customer_name,
            issue_types=issue_types,
            priority=priority,
            summary="Customer reports a possible billing issue and an invoice export failure.",
            confidence=0.92,
        )

    def analyze(self, triage: TriageResult, evidence: list[Evidence]) -> RootCause:
        facts = " ".join(item.fact.lower() for item in evidence)
        causes = []
        findings = []
        if "two successful payments" in facts:
            findings.append("Two successful payments map to the same invoice and amount.")
            causes.append("Duplicate payment was captured for a single invoice.")
        if "timed out" in facts:
            findings.append("The invoice export worker timed out repeatedly.")
            causes.append("A large invoice exceeded the export worker's 30-second timeout.")
        if not causes:
            causes.append("Available evidence is insufficient for a confident diagnosis.")
        return RootCause(
            findings=findings, root_causes=causes, confidence=0.95 if findings else 0.35
        )

    def plan(self, triage: TriageResult, root_cause: RootCause) -> ResolutionPlan:
        actions = []
        causes = " ".join(root_cause.root_causes).lower()
        if "duplicate payment" in causes:
            actions.append(
                ProposedAction(
                    action="issue_account_credit",
                    reason="Reverse the verified duplicate payment while preserving an audit trail.",
                    parameters={"amount": 120.0, "currency": "USD"},
                    risk="high",
                )
            )
        if "export worker" in causes:
            actions.append(
                ProposedAction(
                    action="retry_invoice_export",
                    reason="Retry the export through the large-document worker.",
                    parameters={"invoice_id": "inv_3021", "queue": "large-document"},
                    risk="low",
                )
            )
        actions.append(
            ProposedAction(
                action="update_ticket",
                reason="Record the investigation and current status.",
                parameters={"status": "pending_approval"},
                risk="low",
            )
        )
        return ResolutionPlan(
            customer_summary="We found a duplicate charge and a timeout affecting the invoice export.",
            internal_summary="Issue credit after approval, retry export safely, then verify both outcomes.",
            actions=actions,
        )


class OpenAIReasoner:
    """Optional provider demonstrating schema-constrained model output."""

    def __init__(self, model: str) -> None:
        from langchain_openai import ChatOpenAI

        self._model = ChatOpenAI(model=model, temperature=0)

    def triage(self, subject: str, body: str) -> TriageResult:
        model = self._model.with_structured_output(TriageResult)
        return model.invoke(
            [
                ("system", "Triage this B2B SaaS support ticket. Do not invent missing facts."),
                ("human", f"Subject: {subject}\n\nBody: {body}"),
            ]
        )

    def analyze(self, triage: TriageResult, evidence: list[Evidence]) -> RootCause:
        model = self._model.with_structured_output(RootCause)
        return model.invoke(
            [
                (
                    "system",
                    "Identify root causes using only supplied evidence. State uncertainty explicitly.",
                ),
                (
                    "human",
                    json.dumps(
                        {
                            "triage": triage.model_dump(),
                            "evidence": [item.model_dump() for item in evidence],
                        }
                    ),
                ),
            ]
        )

    def plan(self, triage: TriageResult, root_cause: RootCause) -> ResolutionPlan:
        model = self._model.with_structured_output(ResolutionPlan)
        return model.invoke(
            [
                (
                    "system",
                    "Create the smallest safe resolution plan. Never claim an action already happened.",
                ),
                (
                    "human",
                    json.dumps(
                        {
                            "triage": triage.model_dump(),
                            "root_cause": root_cause.model_dump(),
                        }
                    ),
                ),
            ]
        )
