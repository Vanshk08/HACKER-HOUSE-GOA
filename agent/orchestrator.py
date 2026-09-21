# agent/orchestrator.py

from langgraph.graph import StateGraph, START, END

try:
    from agent.state import InvestigationState
    from agent.investigator import InvestigationAgent
    from agent.tool_executor import ToolExecutor
    from agent.assessment import AssessmentAgent
    from agent.policy import PolicyAgent
except ImportError:
    from state import InvestigationState
    from investigator import InvestigationAgent
    from tool_executor import ToolExecutor
    from assessment import AssessmentAgent
    from policy import PolicyAgent


def should_continue(state: InvestigationState):
    max_iterations = state.get("max_iterations", 10)
    iteration_count = state.get("iteration_count", 0)

    if iteration_count >= max_iterations:
        return "assessment"

    if state.get("stop", False):
        return "assessment"

    messages = state.get("messages", [])

    if not messages:
        return "assessment"

    last_message = messages[-1]

    if getattr(last_message, "tool_calls", None):
        return "continue"

    return "assessment"


def build_investigation_graph(
    llm=None,
    investigator=None,
    assessment=None,
    assessment_llm=None,
    policy=None,
    policy_agent=None,
    policy_llm=None,
):

    if investigator is None:
        if llm is None:
            try:
                from agent.llm_engine import get_investigator_llm
                llm = get_investigator_llm()
            except Exception:
                try:
                    from agent.llm_engine import AutonomousInvestigatorLLM
                    llm = AutonomousInvestigatorLLM()
                except ImportError:
                    from llm_engine import AutonomousInvestigatorLLM
                    llm = AutonomousInvestigatorLLM()
        investigator = InvestigationAgent(llm)

    tool_executor = ToolExecutor()

    if assessment is None:
        if assessment_llm is None:
            if hasattr(llm, "with_structured_output"):
                ass_llm = llm
            else:
                try:
                    from agent.llm_engine import get_assessment_llm
                    ass_llm = get_assessment_llm()
                except Exception:
                    try:
                        from agent.llm_engine import AutonomousAssessmentLLM
                        ass_llm = AutonomousAssessmentLLM()
                    except ImportError:
                        from llm_engine import AutonomousAssessmentLLM
                        ass_llm = AutonomousAssessmentLLM()
        else:
            ass_llm = assessment_llm
        assessment = AssessmentAgent(ass_llm)

    if policy is None:
        policy = policy_agent or PolicyAgent(llm=policy_llm)

    graph = StateGraph(InvestigationState)

    graph.add_node(
        "investigator",
        investigator.node,
    )

    graph.add_node(
        "tool_executor",
        tool_executor.node,
    )

    graph.add_node(
        "assessment",
        assessment.node,
    )

    graph.add_node(
        "policy",
        policy.node,
    )

    graph.add_edge(
        START,
        "investigator",
    )

    graph.add_conditional_edges(
        "investigator",
        should_continue,
        {
            "continue": "tool_executor",
            "assessment": "assessment",
        },
    )

    graph.add_edge(
        "tool_executor",
        "investigator",
    )

    graph.add_edge(
        "assessment",
        "policy",
    )

    graph.add_edge(
        "policy",
        END,
    )

    return graph.compile()


class InvestigationOrchestrator:
    """
    Orchestrator that wraps the LangGraph compiled StateGraph.
    Executes the Investigation + Assessment workflow.
    """

    def __init__(
        self,
        llm_or_investigator,
        assessment_agent=None,
        assessment_llm=None,
        policy_agent=None,
        policy_llm=None,
    ):
        if hasattr(llm_or_investigator, "node"):
            self.graph = build_investigation_graph(
                investigator=llm_or_investigator,
                assessment=assessment_agent,
                assessment_llm=assessment_llm,
                policy=policy_agent,
                policy_llm=policy_llm,
            )
        else:
            self.graph = build_investigation_graph(
                llm=llm_or_investigator,
                assessment=assessment_agent,
                assessment_llm=assessment_llm,
                policy=policy_agent,
                policy_llm=policy_llm,
            )

    def run(self, state: InvestigationState):
        return self.graph.invoke(state)
