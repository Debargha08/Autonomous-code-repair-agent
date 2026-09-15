from typing import TypedDict


class AgentState(TypedDict):
    task: str
    repository_path: str

    plan: list[str]

    relevant_files: list[str]

    observations: list[str]

    changes: list[str]

    test_results: str

    reflection: str

    retry_count: int

    status: str