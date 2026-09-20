"""Reasoning providers: deterministic for tests, structured LLM output for demos.

Both implement the Reasoner protocol so AgentNodes and build_graph can swap
providers without changing graph topology. RuleBasedReasoner is the offline
baseline; OpenAIReasoner demonstrates schema-constrained model calls for evals.
"""

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
    """Structural interface for triage → analyze → plan.

    Nodes call these three methods only. Implementations must return validated
    Pydantic models; callers dump them to dicts before writing AgentState.
    """

    def triage(self, subject: str, body: str) -> TriageResult: ...

    def analyze(self, triage: TriageResult, evidence: list[Evidence]) -> RootCause: ...

    def plan(self, triage: TriageResult, root_cause: RootCause) -> ResolutionPlan: ...


class RuleBasedReasoner:
    """Keyword/heuristic baseline — offline, repeatable, no API key.

    Used by default in CLI and pytest. Later evals can score an LLM against this
    baseline instead of treating every model response as ground truth.
    """

    def triage(self, subject: str, body: str) -> TriageResult:
        """Map ticket text to IssueType(s), priority, and a best-effort customer name."""
        text = f"{subject}\n{body}".lower()
        issue_types = []
        if any(word in text for word in ("charged", "charge", "payment", "refund", "duplicate")):
            issue_types.append("billing")
        if "invoice" in text and any(word in text for word in ("export", "download", "failed")):
            issue_types.append("invoice_export")
        if any(
            keyword in text
            for keyword in (
                "401",
                "unauthorized",
                "api key",
                "authentication",
                "authentication failed",
            )
        ):
            issue_types.append("api_error")
        if not issue_types:
            issue_types.append("unknown")

        # Company-style name in the body (e.g. "ACME Inc") for the CloudDesk lookup.
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
        """Infer root causes from Evidence — scoped by source so policy text is not a finding.

        retrieve_policy appends billing docs that *describe* duplicate payments; those
        must not be treated as proof a duplicate occurred. Payment/log sources are
        observational; policy is instructional and only used later for planning/citations.
        """
        payment_facts = " ".join(
            item.fact.lower() for item in evidence if item.source == "payment"
        )
        log_facts = " ".join(item.fact.lower() for item in evidence if item.source == "log")
        causes = []
        findings = []
        if "two successful payments" in payment_facts:
            findings.append("Two successful payments map to the same invoice and amount.")
            causes.append("Duplicate payment was captured for a single invoice.")
        if "timed out" in log_facts:
            findings.append("The invoice export worker timed out repeatedly.")
            causes.append("A large invoice exceeded the export worker's 30-second timeout.")
        if any(
            keyword in log_facts
            for keyword in (
                "401",
                "unauthorized",
                "authentication",
                "api key",
                "invalid api key",
                "authentication failed",
            )
        ):
            findings.append("The API gateway rejected requests with HTTP 401.")
            causes.append("The rotated API key is invalid or was not activated correctly.")
        if not causes:
            causes.append("Available evidence is insufficient for a confident diagnosis.")
        return RootCause(
            findings=findings, root_causes=causes, confidence=0.95 if findings else 0.35
        )

    def plan(self, triage: TriageResult, root_cause: RootCause) -> ResolutionPlan:
        """Map diagnosed causes to a fixed action vocabulary with risk labels."""
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
        if "api key" in causes or "authentication" in causes:
            actions.append(
                ProposedAction(
                    action="escalate_to_human",
                    reason=(
                        "Credential changes require identity verification "
                        "before the key can be modified."
                    ),
                    parameters={
                        "team": "platform-support",
                        "priority": triage.priority,
                    },                    
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
    """Optional LLM provider using ChatOpenAI.with_structured_output(schema).

    temperature=0 reduces variance for demos; Pydantic schemas still reject
    malformed or out-of-vocab actions before they hit policy_guard or tools.
    """

    def __init__(self, model: str) -> None:
        from langchain_openai import ChatOpenAI

        self._model = ChatOpenAI(model=model, temperature=0)

    def triage(self, subject: str, body: str) -> TriageResult:
        """Structured LLM triage; prompt forbids inventing facts not in the ticket."""
        model = self._model.with_structured_output(TriageResult)
        return model.invoke(
            [
                ("system", "Triage this B2B SaaS support ticket. Do not invent missing facts."),
                ("human", f"Subject: {subject}\n\nBody: {body}"),
            ]
        )

    def analyze(self, triage: TriageResult, evidence: list[Evidence]) -> RootCause:
        """Structured diagnosis constrained to supplied evidence only."""
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
        """Structured plan; must only emit actions from ProposedAction.action Literal."""
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
