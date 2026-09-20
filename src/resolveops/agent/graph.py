"""Explicit workflow topology for ResolveOps Day 1.

Builds a StateGraph with fixed edges (not an autonomous agent loop). Explicit
steps make sensitive-action gates, human approval interrupts, and resume-from-
checkpoint tractable later. InMemorySaver stores per-thread state for Day 1;
Day 5 swaps this for a durable Postgres checkpointer.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from resolveops.agent.nodes import AgentNodes
from resolveops.agent.reasoning import Reasoner, RuleBasedReasoner
from resolveops.services.mock_cloudesk import MockCloudDeskService
from resolveops.state import AgentState


def build_graph(reasoner: Reasoner | None = None):
    """Wire nodes, edges, and a checkpointer into a compiled runnable graph.

    Dependencies (reasoner, CloudDesk) are injected into AgentNodes so tests can
    swap providers without rebuilding topology. Returns a CompiledStateGraph that
    supports invoke/stream and get_state for the final checkpoint.
    """
    nodes = AgentNodes(
        reasoner=reasoner or RuleBasedReasoner(),
        cloudesk=MockCloudDeskService(),
    )
    builder = StateGraph(AgentState)
    builder.add_node("triage_ticket", nodes.triage_ticket)
    builder.add_node("investigate_customer", nodes.investigate_customer)
    builder.add_node("retrieve_policy", nodes.retrieve_policy)
    builder.add_node("analyze_root_cause", nodes.analyze_root_cause)
    builder.add_node("generate_resolution_plan", nodes.generate_resolution_plan)
    builder.add_node("policy_guard", nodes.policy_guard)

    # Linear Day-1 path: each edge is unconditional. Conditional routing (e.g. missing
    # customer → escalate) is intentionally deferred to exercises / later days.
    builder.add_edge(START, "triage_ticket")
    builder.add_edge("triage_ticket", "investigate_customer")
    builder.add_edge("investigate_customer", "retrieve_policy")
    builder.add_edge("retrieve_policy", "analyze_root_cause")
    builder.add_edge("analyze_root_cause", "generate_resolution_plan")
    builder.add_edge("generate_resolution_plan", "policy_guard")
    builder.add_edge("policy_guard", END)
    return builder.compile(checkpointer=InMemorySaver())
