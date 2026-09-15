from langchain_ollama import ChatOllama

from app.tools.file_tools import read_file


llm = ChatOllama(
    model="qwen2.5:7b",
    temperature=0
)


def repair_code(state):

    repository_path = state["repository_path"]
    observations = state["observations"]
    task = state["task"]
    reflection = state.get("reflection", "")
    test_results = state.get("test_results", "")

    changes = []

    print("\n================ CODER ================\n")

    for observation in observations:

        if "BUG FOUND:" not in observation:
            continue

        lines = observation.splitlines()

        file_path = None

        for line in lines:

            if line.startswith("File:"):
                file_path = line.replace("File:", "").strip()
                break

        if not file_path:

            print("Could not determine file path.")
            continue

        print(f"Repairing: {file_path}")

        code = read_file(
            repository_path,
            file_path
        )

        prompt = f"""
You are an autonomous software repair engineer.

Your job is to repair the source code so that the repository tests pass.

================ USER TASK ================

{task}

================ TARGET FILE ================

{file_path}

================ CURRENT SOURCE CODE ================

{code}

================ ANALYZER REPORT ================

{observation}

================ TEST RESULTS ================

{test_results}

================ REFLECTOR INSTRUCTIONS ================

{reflection}

=============================================

STRICT REPAIR RULES:

1. The existing tests are the specification of required behavior.
2. Fix the source code so that those tests pass.
3. Use the exact values and expected outputs shown by the tests.
4. Do NOT invent databases, APIs, external services, files, or
   configuration unless the repository explicitly requires them.
5. Do NOT modify the tests.
6. Do NOT change the test expectations.
7. Preserve existing functionality where possible.
8. Make the smallest correct repair.
9. Return the COMPLETE corrected source file.
10. Return ONLY source code.
11. Do NOT use Markdown.
12. Do NOT include explanations.

Before producing the code, reason internally about every failing test
and ensure the implementation satisfies all of them.

Return ONLY the corrected source code.
"""

        response = llm.invoke(prompt)

        repaired_code = response.content.strip()

        if repaired_code.startswith("```"):

            lines = repaired_code.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            repaired_code = "\n".join(lines).strip()

        full_path = f"{repository_path}/{file_path}"

        with open(
            full_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(
                repaired_code + "\n"
            )

        changes.append(
            f"Repaired {file_path}"
        )

        print(f"✓ Repaired {file_path}")

    print("\n=======================================\n")

    return {
        "changes": changes,
        "status": "repair_complete"
    }