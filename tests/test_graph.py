import uuid

from resolveops.agent.graph import build_graph

TICKET = (
    "ACME Inc says the invoice export failed three times. They believe they were charged "
    "twice, and this is blocking their finance team before tomorrow."
)


def run_graph():
    graph = build_graph()
    return graph.invoke(
        {
            "ticket_id": "ticket_test",
            "subject": "Duplicate charge and failed invoice export",
            "body": TICKET,
            "evidence": [],
            "trace": [],
            "status": "received",
        },
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )


def test_graph_finds_both_issues():
    state = run_graph()
    assert set(state["triage"]["issue_types"]) == {"billing", "invoice_export"}
    assert state["root_cause"]["confidence"] >= 0.9


def test_sensitive_financial_action_requires_approval():
    state = run_graph()
    actions = [item["action"] for item in state["resolution_plan"]["actions"]]
    assert "issue_account_credit" in actions
    assert state["approval_required"] is True
    assert state["status"] == "awaiting_approval"


def test_trace_contains_every_graph_node():
    state = run_graph()
    stages = [item["stage"] for item in state["trace"]]
    assert stages == [
        "triage_ticket",
        "investigate_customer",
        "retrieve_policy",
        "analyze_root_cause",
        "generate_resolution_plan",
        "policy_guard",
    ]
