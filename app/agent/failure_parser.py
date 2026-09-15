import ast
import re


def parse_value(value):
    value = value.strip()

    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def parse_arguments(argument_text):
    if not argument_text.strip():
        return []

    try:
        tree = ast.parse(
            f"f({argument_text})",
            mode="eval"
        ).body

        arguments = []

        for argument in tree.args:
            try:
                arguments.append(ast.literal_eval(argument))
            except (ValueError, SyntaxError):
                arguments.append(ast.unparse(argument))

        return arguments

    except (ValueError, SyntaxError):
        return []


def parse_test_failures(test_output):
    failures = []
    lines = test_output.splitlines()

    in_failures_section = False
    current_failure = None

    for line in lines:

        # ---------------------------------------------------------
        # Start of detailed failure section
        # ---------------------------------------------------------
        if "FAILURES" in line and "=" in line:
            in_failures_section = True
            continue

        if not in_failures_section:
            continue

        # ---------------------------------------------------------
        # End of detailed failure section
        # ---------------------------------------------------------
        if "short test summary info" in line:
            break

        # ---------------------------------------------------------
        # Detect pytest failure heading
        #
        # Example:
        # _______________________________ test_basic_total _______________________________
        # ---------------------------------------------------------
        heading_match = re.search(
            r"\b(test_[A-Za-z0-9_]+)\b",
            line
        )

        if (
            heading_match
            and line.strip().startswith("_")
            and line.strip().endswith("_")
        ):
            if current_failure is not None:
                failures.append(current_failure)

            current_failure = {
                "test_file": None,
                "test_name": heading_match.group(1),
                "error_type": None,
                "error_message": None,
                "function": None,
                "arguments": [],
                "expected": None,
                "actual": None,
            }

            continue

        if current_failure is None:
            continue

        # ---------------------------------------------------------
        # Assertion expression
        #
        # >       assert calculate_total(100, 3) == 300
        # ---------------------------------------------------------
        assertion_match = re.search(
            r">\s+assert\s+(.+)",
            line
        )

        if assertion_match:
            expression = assertion_match.group(1).strip()

            try:
                tree = ast.parse(expression, mode="eval").body

                if isinstance(tree, ast.Compare):

                    # Function call
                    if isinstance(tree.left, ast.Call):
                        if isinstance(tree.left.func, ast.Name):

                            current_failure["function"] = (
                                tree.left.func.id
                            )

                            arguments = []

                            for argument in tree.left.args:
                                try:
                                    arguments.append(
                                        ast.literal_eval(argument)
                                    )
                                except (ValueError, SyntaxError):
                                    arguments.append(
                                        ast.unparse(argument)
                                    )

                            current_failure["arguments"] = arguments

                    # Expected value
                    if len(tree.comparators) == 1:
                        current_failure["expected"] = parse_value(
                            ast.unparse(tree.comparators[0])
                        )

            except SyntaxError:
                pass

            continue

        # ---------------------------------------------------------
        # Actual value + function call
        #
        # E        + where 97 = calculate_total(100, 3)
        # ---------------------------------------------------------
        where_match = re.search(
            r"\+\s+where\s+(.+?)\s*=\s*"
            r"([A-Za-z_][A-Za-z0-9_]*)\((.*)\)",
            line
        )

        if where_match:

            actual_value = where_match.group(1).strip()
            function_name = where_match.group(2).strip()
            argument_text = where_match.group(3).strip()

            current_failure["actual"] = parse_value(actual_value)

            if current_failure["function"] is None:
                current_failure["function"] = function_name

            if not current_failure["arguments"]:
                current_failure["arguments"] = parse_arguments(
                    argument_text
                )

            continue

        # ---------------------------------------------------------
        # Test source location
        #
        # sandbox/.../test_calculator.py:5: AssertionError
        # ---------------------------------------------------------
        location_match = re.match(
            r"^(.+\.py):(\d+):\s*(\w+)",
            line.strip()
        )

        if location_match:

            current_failure["test_file"] = (
                location_match.group(1)
            )

            current_failure["error_type"] = (
                location_match.group(3)
            )

            current_failure["error_message"] = (
                line.strip()
            )

            continue

    # -------------------------------------------------------------
    # Store final failure
    # -------------------------------------------------------------
    if current_failure is not None:
        failures.append(current_failure)

    return failures
