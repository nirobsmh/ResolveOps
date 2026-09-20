"""Behavioral guarantees for the Day-1 linear graph with RuleBasedReasoner.

These assert product contracts interviewers care about: multi-issue triage,
financial actions blocked behind approval, and a complete auditable node trace.
No API key required — build_graph defaults to the deterministic reasoner.
"""

import uuid

from resolveops.agent.graph import build_graph

TICKET = (
    "ACME Inc says the invoice export failed three times. They believe they were charged "
    "twice, and this is blocking their finance team before tomorrow."
)


def run_graph():
    """Invoke a fresh thread so checkpoint state never leaks across tests."""
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
    """Triage must surface billing + invoice_export; diagnosis should be high-confidence."""
    state = run_graph()
    assert set(state["triage"]["issue_types"]) == {"billing", "invoice_export"}
    assert state["root_cause"]["confidence"] >= 0.9


def test_sensitive_financial_action_requires_approval():
    """issue_account_credit may be proposed, but policy_guard must require human approval."""
    state = run_graph()
    actions = [item["action"] for item in state["resolution_plan"]["actions"]]
    assert "issue_account_credit" in actions
    assert state["approval_required"] is True
    assert state["status"] == "awaiting_approval"


def test_trace_contains_every_graph_node():
    """Trace order mirrors graph edges — useful for UI and failure debugging later."""
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

def test_api_authentication_failure_does_not_propose_financial_action():
    graph = build_graph()

    state = graph.invoke(
        {
            "ticket_id": "ticket_api_001",
            "subject": "API authentication failure",
            "body": (
                "Globex LLC receives 401 Unauthorized errors "
                "after rotating its API key."
            ),
            "evidence": [],
            "trace": [],
            "status": "received",
        },
        config={
            "configurable": {
                "thread_id": "api-auth-test",
            }
        },
    )

    assert "api_error" in state["triage"]["issue_types"]

    actions = [
        action["action"]
        for action in state["resolution_plan"]["actions"]
    ]

    assert "escalate_to_human" in actions
    assert "issue_account_credit" not in actions
    assert state["approval_required"] is False