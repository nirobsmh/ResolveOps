"""Node factory. Dependencies are injected so orchestration stays testable."""

from pathlib import Path

from resolveops.agent.reasoning import Reasoner
from resolveops.schemas import Evidence, ResolutionPlan, RootCause, TraceEvent, TriageResult
from resolveops.services.mock_cloudesk import MockCloudDeskService
from resolveops.state import AgentState


def _trace(stage: str, summary: str, **details: object) -> dict[str, object]:
    return TraceEvent(stage=stage, summary=summary, details=details).model_dump()


class AgentNodes:
    def __init__(self, reasoner: Reasoner, cloudesk: MockCloudDeskService) -> None:
        self.reasoner = reasoner
        self.cloudesk = cloudesk

    def triage_ticket(self, state: AgentState) -> dict[str, object]:
        triage = self.reasoner.triage(state["subject"], state["body"])
        return {
            "triage": triage.model_dump(),
            "status": "triaged",
            "trace": [
                _trace(
                    "triage_ticket",
                    f"Classified as {', '.join(triage.issue_types)}",
                    priority=triage.priority,
                    confidence=triage.confidence,
                )
            ],
        }

    def investigate_customer(self, state: AgentState) -> dict[str, object]:
        triage = TriageResult.model_validate(state["triage"])
        customer = self.cloudesk.find_customer_by_name(triage.customer_name)
        if not customer:
            evidence = [
                Evidence(
                    source="customer",
                    reference="not_found",
                    fact="No customer record matched the extracted customer name.",
                )
            ]
            return {
                "customer": {},
                "invoices": [],
                "payments": [],
                "logs": [],
                "evidence": [item.model_dump() for item in evidence],
                "trace": [_trace("investigate_customer", "Customer record was not found")],
            }

        customer_id = str(customer["id"])
        invoices = self.cloudesk.get_recent_invoices(customer_id)
        payments = self.cloudesk.get_payment_history(customer_id)
        logs = self.cloudesk.search_logs(customer_id)
        evidence = [
            Evidence(
                source="customer",
                reference=customer_id,
                fact=f"Customer is active on the {customer['plan']} plan.",
            )
        ]
        if len(payments) >= 2:
            first, second = payments[0], payments[1]
            same_charge = (
                first["invoice_id"] == second["invoice_id"]
                and first["amount"] == second["amount"]
                and first["status"] == second["status"] == "succeeded"
            )
            if same_charge:
                evidence.append(
                    Evidence(
                        source="payment",
                        reference=f"{first['id']},{second['id']}",
                        fact=(
                            f"Two successful payments of {first['amount']} {first['currency']} "
                            f"map to invoice {first['invoice_id']}."
                        ),
                    )
                )
        for log in logs:
            evidence.append(
                Evidence(source="log", reference=str(log["id"]), fact=str(log["message"]))
            )
        return {
            "customer": customer,
            "invoices": invoices,
            "payments": payments,
            "logs": logs,
            "evidence": [item.model_dump() for item in evidence],
            "status": "investigated",
            "trace": [
                _trace(
                    "investigate_customer",
                    "Collected account, invoice, payment, and application-log evidence",
                    tools=[
                        "find_customer_by_name",
                        "get_recent_invoices",
                        "get_payment_history",
                        "search_logs",
                    ],
                    evidence_count=len(evidence),
                )
            ],
        }

    def retrieve_policy(self, state: AgentState) -> dict[str, object]:
        knowledge_dir = Path(__file__).resolve().parents[3] / "data" / "knowledge"
        passages = []
        evidence = []
        for path in sorted(knowledge_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if any(
                keyword in text.lower() for keyword in ("duplicate", "credit", "invoice export")
            ):
                passages.append({"document": path.name, "content": text.strip()})
                evidence.append(
                    Evidence(
                        source="policy",
                        reference=path.name,
                        fact=text.strip().replace("\n", " "),
                    )
                )
        return {
            "policy_passages": passages,
            "evidence": [item.model_dump() for item in evidence],
            "trace": [
                _trace(
                    "retrieve_policy",
                    f"Retrieved {len(passages)} relevant policy documents",
                    documents=[item["document"] for item in passages],
                )
            ],
        }

    def analyze_root_cause(self, state: AgentState) -> dict[str, object]:
        triage = TriageResult.model_validate(state["triage"])
        evidence = [Evidence.model_validate(item) for item in state.get("evidence", [])]
        root_cause = self.reasoner.analyze(triage, evidence)
        return {
            "root_cause": root_cause.model_dump(),
            "status": "diagnosed",
            "trace": [
                _trace(
                    "analyze_root_cause",
                    "; ".join(root_cause.root_causes),
                    confidence=root_cause.confidence,
                )
            ],
        }

    def generate_resolution_plan(self, state: AgentState) -> dict[str, object]:
        triage = TriageResult.model_validate(state["triage"])
        root_cause = RootCause.model_validate(state["root_cause"])
        plan = self.reasoner.plan(triage, root_cause)
        return {
            "resolution_plan": plan.model_dump(),
            "status": "planned",
            "trace": [
                _trace(
                    "generate_resolution_plan",
                    f"Proposed {len(plan.actions)} actions",
                    actions=[action.action for action in plan.actions],
                )
            ],
        }

    def policy_guard(self, state: AgentState) -> dict[str, object]:
        sensitive = {"issue_account_credit", "send_customer_email"}
        plan = ResolutionPlan.model_validate(state["resolution_plan"])
        blocked_actions = [
            action.action
            for action in plan.actions
            if action.action in sensitive or action.risk == "high"
        ]
        approval_required = bool(blocked_actions)
        status = "awaiting_approval" if approval_required else "ready_to_execute"
        return {
            "approval_required": approval_required,
            "status": status,
            "trace": [
                _trace(
                    "policy_guard",
                    "Human approval required" if approval_required else "Plan is safe to execute",
                    blocked_actions=blocked_actions,
                )
            ],
        }
