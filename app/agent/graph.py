from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.planner import create_plan
from app.agent.scanner import scan_repository
from app.agent.analyzer import analyze_code
from app.agent.coder import repair_code
from app.agent.test_runner import run_tests
from app.agent.reflector import reflect_on_failure


MAX_RETRIES = 3


def should_retry(state):

    test_results = state.get(
        "test_results",
        ""
    )

    retry_count = state.get(
        "retry_count",
        0
    )

    status = state.get(
        "status",
        ""
    )

    if status == "tests_passed":
        return "end"

    if retry_count >= MAX_RETRIES:
        return "end"

    if status == "tests_failed":
        return "reflector"

    return "end"


def increment_retry(state):

    retry_count = state.get(
        "retry_count",
        0
    )

    return {
        "retry_count": retry_count + 1
    }


def build_reflector_context(state):

    repository_path = state[
        "repository_path"
    ]

    observations = state.get(
        "observations",
        []
    )

    source_file = None
    function_name = None
    error_message = None

    for observation in observations:

        if "BUG FOUND:" not in observation:
            continue

        lines = observation.splitlines()

        for line in lines:

            if line.startswith("File:"):

                source_file = (
                    line.replace(
                        "File:",
                        ""
                    ).strip()
                )

                break

        if source_file:
            break

    if not source_file:

        return {
            "reflection": (
                "Unable to determine the "
                "repair target from the analyzer output."
            )
        }

    repair_context = {
        "source_file": source_file,
        "function": function_name,
        "start_line": None,
        "end_line": None,
        "exists": True,
        "error_type": None,
        "error_message": error_message,
        "behaviors": []
    }

    targeted_results = [
        {
            "test": "repository_tests",
            "status": state.get(
                "status",
                "tests_failed"
            ),
            "output": state.get(
                "test_results",
                ""
            )
        }
    ]

    reflection_result = reflect_on_failure(
        repository_path,
        state.get(
            "task",
            "Repair the failing source code."
        ),
        repair_context,
        targeted_results
    )

    return {
        "reflection": reflection_result.get(
            "reflection",
            ""
        )
    }


def build_graph():

    builder = StateGraph(
        AgentState
    )

    builder.add_node(
        "planner",
        create_plan
    )

    builder.add_node(
        "scanner",
        scan_repository
    )

    builder.add_node(
        "analyzer",
        analyze_code
    )

    builder.add_node(
        "coder",
        repair_code
    )

    builder.add_node(
        "test_runner",
        run_tests
    )

    builder.add_node(
        "reflector",
        build_reflector_context
    )

    builder.add_node(
        "increment_retry",
        increment_retry
    )

    builder.add_edge(
        START,
        "planner"
    )

    builder.add_edge(
        "planner",
        "scanner"
    )

    builder.add_edge(
        "scanner",
        "analyzer"
    )

    builder.add_edge(
        "analyzer",
        "coder"
    )

    builder.add_edge(
        "coder",
        "test_runner"
    )

    builder.add_conditional_edges(
        "test_runner",
        should_retry,
        {
            "reflector": "reflector",
            "end": END
        }
    )

    builder.add_edge(
        "reflector",
        "increment_retry"
    )

    builder.add_edge(
        "increment_retry",
        "coder"
    )

    return builder.compile()
