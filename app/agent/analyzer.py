from langchain_ollama import ChatOllama

from app.tools.file_tools import read_file


llm = ChatOllama(
    model="qwen2.5:7b",
    temperature=0
)


def analyze_code(state):

    repository_path = state["repository_path"]
    relevant_files = state["relevant_files"]
    task = state["task"]

    observations = []

    for file_path in relevant_files:

        if file_path.endswith("__init__.py") or file_path.endswith("_init__.py"):
            continue

        code = read_file(repository_path, file_path)

        print(f"\nAnalyzing: {file_path}")

        # Detect empty source files directly
        if not code.strip():

            observation = f"""
File: {file_path}

BUG FOUND:
The file is empty.

Root cause:
The target source file does not contain the required implementation.

Required repair:
Implement the functionality required by the user's task and the existing tests.
"""

            observations.append(observation)

            print(observation)

            continue

        prompt = f"""
You are a senior software engineer and debugging expert.

Analyze this source file for bugs related to the user's task.

User task:
{task}

File:
{file_path}

Source code:
{code}

Determine:

1. Whether this file is relevant to the task.
2. The exact bug, if one exists.
3. The root cause.
4. The exact logic that needs to change.
5. A concise recommended fix.

If there is no bug, say:
NO BUG FOUND

Be precise and concise.
Do not rewrite the entire file.
"""

        response = llm.invoke(prompt)

        observations.append(
            f"File: {file_path}\n{response.content}"
        )

    return {
        "observations": observations,
        "status": "analysis_complete"
    }