from langchain_ollama import ChatOllama

from app.tools.file_tools import read_file


llm = ChatOllama(
    model="qwen2.5:7b",
    temperature=0
)


def reflect_on_failure(
    repository_path,
    task,
    repair_context,
    targeted_results
):
    source_file = repair_context.get(
        "source_file"
    )

    function_name = repair_context.get(
        "function"
    )

    try:
        source_code = read_file(
            repository_path,
            source_file
        )
    except Exception:
        source_code = (
            "Source code could not be read."
        )

    behavior_lines = []

    for index, behavior in enumerate(
        repair_context.get("behaviors", []),
        start=1
    ):
        behavior_lines.append(
            f"""
Behavior {index}:

Test:
{behavior.get("test_name")}

Assertion:
{behavior.get("assertion")}

Arguments:
{behavior.get("arguments")}

Expected:
{behavior.get("expected")}

Previous actual result:
{behavior.get("actual")}
"""
        )

    behavior_specification = (
        "\n".join(behavior_lines)
    )

    test_output_lines = []

    for result in targeted_results:
        test_output_lines.append(
            f"""
Test:
{result.get("test")}

Status:
{result.get("status")}

Output:
{result.get("output")}
"""
        )

    targeted_output = (
        "\n".join(test_output_lines)
    )

    prompt = f"""
You are a strict autonomous software debugging expert.

A previous AI-generated repair failed its targeted tests.

Your task is to analyze WHY the repair failed and provide
precise instructions for a second repair attempt.

Do NOT write the corrected source code.

================ USER TASK ================

{task}

================ TARGET FILE ================

{source_file}

================ TARGET FUNCTION ================

{function_name}

================ CURRENT SOURCE CODE ================

{source_code}

================ REQUIRED BEHAVIOR ================

{behavior_specification}

================ TARGETED TEST RESULTS ================

{targeted_output}

=============================================

RULES:

1. Treat the tests as the strongest specification.

2. Do not invent requirements.

3. Do not modify tests.

4. Identify exactly why the previous repair failed.

5. Determine what the implementation must do
   to satisfy ALL behavioral requirements.

6. Preserve unrelated existing functionality.

7. Keep the next repair as small as possible.

8. Do not introduce unnecessary dependencies.

9. Do not suggest external services or APIs.

10. Give concrete instructions that another
    coding agent can directly implement.

Return ONLY concise repair instructions.
"""

    print(
        "\n================ REFLECTOR ================\n"
    )

    response = llm.invoke(
        prompt
    )

    reflection = (
        response.content
        .strip()
    )

    print(reflection)

    print(
        "\n============================================\n"
    )

    return {
        "reflection": reflection,
        "status": "reflection_complete"
    }
