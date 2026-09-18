import json

from langchain_ollama import ChatOllama

from app.tools.file_tools import read_file
from app.agent.repair_proposal import parse_repair_proposal


llm = ChatOllama(
    model="qwen2.5:7b",
    temperature=0
)


EXECUTABLE_REPAIR_TYPES = {
    "replace_function",
    "replace_statement",
}


CONTROL_FLOW_TYPES = {
    "If",
    "For",
    "AsyncFor",
    "While",
    "Try",
    "With",
    "AsyncWith",
}


def validate_statement_target(
    proposal,
    statements
):
    """
    Validate that a replace_statement proposal targets
    the most specific executable statement available.

    A control-flow parent must not be selected when the
    proposed replacement is a single statement and a
    nested statement provides a more precise repair target.
    """

    if proposal.get("repair_type") != "replace_statement":
        return

    proposed_path = tuple(
        proposal.get("path", [])
    )

    target = None

    for statement in statements:
        if tuple(statement.get("path", ())) == proposed_path:
            target = statement
            break

    if target is None:
        raise ValueError(
            "Repair generator targeted a statement path "
            "that was not found in the localized statements."
        )

    target_type = target.get("type")

    if target_type not in CONTROL_FLOW_TYPES:
        return

    for statement in statements:
        statement_path = tuple(
            statement.get("path", ())
        )

        if (
            len(statement_path) > len(proposed_path)
            and statement_path[:len(proposed_path)] == proposed_path
            and statement.get("depth", 0) > target.get("depth", 0)
        ):
            raise ValueError(
                "Repair generator selected control-flow "
                f"statement at path {proposed_path}, but a "
                "more specific nested statement exists at "
                f"path {statement_path}. "
                "The nested statement must be targeted."
            )


def extract_reflected_function(reflection, function_name):
    """
    Extract a complete corrected function from Reflector feedback.
    Used when structural repair is required and the Reflector has
    already supplied the corrected function.
    """
    if not reflection:
        return None

    import re

    text = str(reflection)

    pattern = (
        r"```python\s*"
        r"(def\s+" + re.escape(function_name) + r"\s*\([^\n]*\):"
        r".*?)"
        r"\s*```"
    )

    match = re.search(pattern, text, re.DOTALL)

    if match:
        return match.group(1).strip()

    pattern = (
        r"(def\s+" + re.escape(function_name) + r"\s*\([^\n]*\):"
        r".*?)(?=\n\s*(?:def |class )|\Z)"
    )

    match = re.search(pattern, text, re.DOTALL)

    if match:
        return match.group(1).strip()

    return None


def reflection_requires_function_replacement(reflection):
    """
    Detect whether Reflector feedback requires a structural
    control-flow change that cannot be represented safely
    by replace_statement.
    """
    if not reflection:
        return False

    text = str(reflection).lower()

    structural_signals = [
        "add an elif",
        "add an else",
        "add a new if",
        "new branch",
        "new control-flow branch",
        "control-flow structure",
        "add a condition",
        "insert a statement",
        "add a statement",
        "add another statement",
        "change the control flow",
    ]

    return any(
        signal in text
        for signal in structural_signals
    )


def generate_repair(
    repository_path,
    repair_context,
    reflection=None
):
    source_file = repair_context["source_file"]
    function_name = repair_context["function"]

    forced_repair_type = (
        "replace_function"
        if reflection_requires_function_replacement(reflection)
        else None
    )

    code = read_file(
        repository_path,
        source_file
    )

    behaviors = repair_context.get(
        "behaviors",
        []
    )

    statements = repair_context.get(
        "statements",
        []
    )

    statement_lines = []

    for index, statement in enumerate(
        statements,
        start=1
    ):
        statement_lines.append(
            f"""
Statement {index}:

Index:
{statement.get("index")}

Type:
{statement.get("type")}

Structural path:
{statement.get("path")}

Nesting depth:
{statement.get("depth")}

Parent statement:
{statement.get("parent_type")}

Source:
{statement.get("source")}
"""
        )

    statement_specification = "\n".join(
        statement_lines
    )

    behavior_lines = []

    for index, behavior in enumerate(
        behaviors,
        start=1
    ):
        behavior_lines.append(
            f"""
Behavior {index}:

Test:
{behavior.get("test_name")}

Assertion:
{behavior.get("assertion")}

Function arguments:
{behavior.get("arguments")}

Expected result:
{behavior.get("expected")}

Actual result:
{behavior.get("actual")}
"""
        )

    behavior_specification = "\n".join(
        behavior_lines
    )

    reflection_section = ""

    repair_type_instruction = ""

    if forced_repair_type:
        repair_type_instruction = f"""
================ REQUIRED REPAIR TYPE ================

The previous repair attempt was rejected because the
required change cannot safely be represented as a
single statement replacement.

You MUST use:

repair_type: {forced_repair_type}

Do NOT use replace_statement.

Return a complete corrected function.
"""

    if reflection:
        reflection_section = f"""
================ REFLECTOR ANALYSIS ================

The previous repair failed.

The Reflector analyzed the failure and provided
the following instructions:

{reflection}

Use this analysis to produce a corrected repair.

Do not repeat the previous incorrect behavior.

=====================================================
"""

    prompt = f"""
You are an autonomous software repair engineer.

Your task is to repair ONE specific Python function
inside an existing repository.

================ TARGET FILE ================

{source_file}

================ TARGET FUNCTION ================

{function_name}

================ CURRENT SOURCE CODE ================

{code}

================ AVAILABLE STATEMENTS ================

The following statements were identified inside the
target function by AST-based statement localization.

When using replace_statement, the "path" field MUST
refer to one of these exact structural paths.

{statement_specification}

================ TEST BEHAVIOR SPECIFICATION ================

{behavior_specification}

{reflection_section}

{repair_type_instruction}

================ REPAIR OBJECTIVE ================

Repair the target function so that ALL provided test
behaviors are satisfied.

The tests are the primary behavioral specification.

You must consider:

- failing inputs
- expected outputs
- actual outputs
- all listed test cases
- existing behavior that should remain unchanged
- Reflector feedback, when provided

Do not optimize for only one failing test.

================ REPAIR CONSTRAINTS ================

1. Modify ONLY the target function.

2. Do not modify test files.

3. Do not modify test expectations.

4. Do not modify unrelated functions.

5. Preserve correct existing behavior.

6. Make the smallest correct change.

7. Do not introduce unnecessary complexity.

8. Do not add external dependencies.

9. Do not introduce external services.

10. Do not introduce network calls.

11. Do not introduce databases or APIs.

12. Do not add imports.

13. Do not include test code.

14. Do not return multiple possible repairs.

15. The repaired function must preserve its existing
    function name and interface.

================ REPAIR TYPE =================

The repair engine currently supports TWO
executable repair types:

1. replace_function
2. replace_statement

Choose the SMALLEST repair that correctly fixes
the identified failure.

Use replace_statement when:

- the defect is isolated to one statement
- the surrounding function logic is already correct
- changing only one statement is sufficient

Use replace_function when:

- multiple statements must change
- the function structure itself is incorrect
- the defect cannot safely be repaired with one statement
- replacing the complete function is the safer repair

CRITICAL CONTROL-FLOW RULE:

Use replace_function when the repair requires changing the
CONTROL-FLOW STRUCTURE of the function.

Examples of structural changes that REQUIRE replace_function:

- adding an elif branch
- adding a new if branch
- adding an else branch
- removing a branch
- changing an if/elif/else structure
- adding or removing a loop
- changing try/except/finally structure
- adding a new sibling statement to an existing statement
- inserting a statement before or after an existing statement
- changing the order of multiple statements
- changing more than one existing statement

A replace_statement repair may ONLY replace ONE EXISTING
STATEMENT with ONE NEW STATEMENT while preserving the
surrounding control-flow structure.

If the correct repair requires a new sibling statement,
new branch, elif, else, or any other structural change,
DO NOT use replace_statement.

Use replace_function instead and return the COMPLETE
corrected function.

IMPORTANT EXAMPLE:

Current function:

def normalize_score(score):
    if score < 0:
        return 0
    return score

Required behavior:

- score < 0 -> 0
- score > 100 -> 100
- otherwise -> score

The correct repair requires adding a new control-flow
branch:

def normalize_score(score):
    if score < 0:
        return 0
    elif score > 100:
        return 100
    return score

Therefore the repair MUST use:

"repair_type": "replace_function"

It MUST NOT attempt to replace the existing If statement
or nested Return statement with a single statement.

================ OUTPUT CONTRACT ================

Return EXACTLY one JSON object.

For replace_function, return:

{{
    "repair_type": "replace_function",
    "function": "{function_name}",
    "code": "COMPLETE REPAIRED FUNCTION SOURCE"
}}

For replace_statement, return:

{{
    "repair_type": "replace_statement",
    "function": "{function_name}",
    "path": [EXACT_PATH_FROM_AVAILABLE_STATEMENTS],
    "code": "ONE REPLACEMENT PYTHON STATEMENT"
}}

The value of "path" MUST be a JSON array containing
the exact structural path copied from AVAILABLE
STATEMENTS.

IMPORTANT:
"EXACT_PATH_FROM_AVAILABLE_STATEMENTS" above is a
placeholder describing the required JSON array.
It MUST NOT appear literally in the output.

For example, if AVAILABLE STATEMENTS contains:

Structural path:
(1,)

then the JSON output MUST contain:

"path": [1]

If AVAILABLE STATEMENTS contains:

Structural path:
(1, "body", 2)

then the JSON output MUST contain:

"path": [1, "body", 2]

================ FIELD REQUIREMENTS ================

repair_type:

    Must be exactly one of:

    "replace_function"
    "replace_statement"

function:

    Must be exactly "{function_name}".

For replace_function:

code:
    Must contain the COMPLETE Python function
    definition for "{function_name}".

The function definition must:

- be syntactically valid Python
- contain the correct function name
- contain the complete function
- preserve the required interface
- implement the required behavior

For replace_statement:

path:
    Must identify EXACTLY ONE existing statement
    inside "{function_name}".

    The path must use the structural AST path
    provided by the repair context.

    IMPORTANT:

    Copy the path EXACTLY from one of the statements
    listed in AVAILABLE STATEMENTS.

    NEVER invent, construct, modify, or extrapolate
    a structural path.

    If the target statement is Statement 1 and its
    localized path is [1], the output path MUST be [1].

    If the target statement has a nested path, copy
    that complete path exactly as provided.

code:
    Must contain EXACTLY ONE valid Python statement.

The replacement statement must:

- be syntactically valid Python
- replace only the statement identified by "path"
- preserve the surrounding function structure
- implement the required behavior
- not contain multiple statements
- not contain a function definition
- not contain imports
- not modify unrelated code

================ STRICT OUTPUT RULES ================

Return ONLY the JSON object.

Do not include:

- Markdown
- code fences
- explanations
- multiple repair proposals
- test code
- imports
- unrelated code

Do NOT return:

- Markdown
- code fences
- explanations
- reasoning
- additional JSON fields
- multiple JSON objects
- imports
- test code
- another function
- text before the JSON
- text after the JSON

The proposal will be validated automatically.

If the proposal violates the contract, it will be rejected.

Return ONLY the JSON object.
"""

    print(
        "\n================ REPAIR GENERATOR ================\n"
    )

    print(
        f"Generating structured repair for: "
        f"{source_file}"
    )

    print(
        f"Target function: {function_name}"
    )

    print(
        f"Behavior specifications: "
        f"{len(behaviors)}"
    )

    print(
        f"Executable repair type: "
        ", ".join(sorted(EXECUTABLE_REPAIR_TYPES))
    )

    if reflection:
        print(
            "Using Reflector feedback: YES"
        )
    else:
        print(
            "Using Reflector feedback: NO"
        )


    response = llm.invoke(prompt)

    raw_output = response.content.strip()

    print(
        "\nRaw proposal received."
    )

    print("Generated proposal:")
    print(raw_output)

    parsed_result = parse_repair_proposal(
        raw_output
    )

    if not parsed_result.get("valid"):
        raise ValueError(
            "Repair generator returned an invalid proposal."
        )

    proposal = parsed_result["proposal"]

    if proposal["repair_type"] not in EXECUTABLE_REPAIR_TYPES:
        raise ValueError(
            "Repair generator returned unsupported "
            f"repair type: {proposal['repair_type']}"
        )

    if proposal["function"] != function_name:
        raise ValueError(
            "Repair generator targeted function "
            f"'{proposal['function']}' instead of "
            f"'{function_name}'."
        )

    # If the Reflector identified a structural repair and
    # supplied a complete corrected function, use that
    # function directly. This prevents the LLM from
    # incorrectly converting a structural repair into
    # replace_statement.

    if reflection_requires_function_replacement(reflection):

        reflected_function = extract_reflected_function(
            reflection,
            function_name
        )

        if reflected_function:

            proposal["repair_type"] = "replace_function"
            proposal.pop("path", None)
            proposal["code"] = reflected_function

            print(
                "\n✓ Structural repair detected."
            )

            print(
                "✓ Using complete function from Reflector."
            )

        else:

            raise ValueError(
                "Reflector identified a structural repair "
                "but did not provide a complete corrected "
                "function."
            )

    # Deterministically resolve an LLM-selected control-flow
    # container to the most specific nested executable statement.
    #
    # Example:
    #   [1]              -> If
    #   [1, "body", 1]   -> Return
    #
    # replace_statement must target the Return, not the If.

    if proposal.get("repair_type") == "replace_statement":

        proposed_path = tuple(proposal.get("path", []))

        matching_statement = next(
            (
                statement
                for statement in statements
                if tuple(statement.get("path", ())) == proposed_path
            ),
            None,
        )

        control_flow_types = {
            "If",
            "For",
            "AsyncFor",
            "While",
            "Try",
            "With",
            "AsyncWith",
        }

        if (
            matching_statement
            and matching_statement.get("type") in control_flow_types
        ):

            nested_statements = [
                statement
                for statement in statements
                if (
                    tuple(statement.get("path", ()))[:len(proposed_path)]
                    == proposed_path
                    and len(tuple(statement.get("path", ())))
                    > len(proposed_path)
                    and statement.get("type") not in control_flow_types
                )
            ]

            if nested_statements:

                nested_statements.sort(
                    key=lambda statement: (
                        len(tuple(statement.get("path", ()))),
                        statement.get("index", 0),
                    )
                )

                selected_statement = nested_statements[0]

                print(
                    "\n⚠ LLM selected control-flow container:"
                )
                print(
                    f"  {proposed_path}"
                    f" ({matching_statement.get('type')})"
                )

                print(
                    "✓ Resolving to nested executable statement:"
                )
                print(
                    f"  {tuple(selected_statement['path'])}"
                    f" ({selected_statement.get('type')})"
                )

                proposal["path"] = list(
                    selected_statement["path"]
                )

    validate_statement_target(
        proposal,
        statements
    )

    repaired_code = proposal["code"].strip()

    if not repaired_code:
        raise ValueError(
            "Repair generator returned empty "
            "function code."
        )

    proposal["code"] = repaired_code

    print(
        "✓ Structured repair proposal validated."
    )

    print(
        f"✓ Repair type: "
        f"{proposal['repair_type']}"
    )

    print(
        f"✓ Target function: "
        f"{proposal['function']}"
    )

    print(
        "\n==================================================\n"
    )

    return proposal
