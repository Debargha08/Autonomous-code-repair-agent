import ast
import os


def normalize_test_file(repository_path, test_file):

    if not test_file:
        return None

    test_file = os.path.normpath(test_file)
    repository_path = os.path.normpath(repository_path)

    repository_name = os.path.basename(repository_path)

    prefix = repository_name + os.sep

    if test_file.startswith(prefix):
        test_file = test_file[len(prefix):]

    return test_file


def extract_function_call_data(
    assertion_node,
    function_name
):

    if not isinstance(
        assertion_node,
        ast.Compare
    ):
        return {
            "arguments": [],
            "expected": None
        }

    function_call = assertion_node.left

    if not isinstance(
        function_call,
        ast.Call
    ):
        return {
            "arguments": [],
            "expected": None
        }

    if not isinstance(
        function_call.func,
        ast.Name
    ):
        return {
            "arguments": [],
            "expected": None
        }

    if (
        function_name is not None
        and function_call.func.id != function_name
    ):
        return {
            "arguments": [],
            "expected": None
        }

    arguments = []

    for argument in function_call.args:

        try:

            arguments.append(
                ast.literal_eval(argument)
            )

        except (
            ValueError,
            TypeError
        ):

            arguments.append(
                ast.unparse(argument)
            )

    expected = None

    if len(assertion_node.comparators) == 1:

        comparator = assertion_node.comparators[0]

        try:

            expected = ast.literal_eval(
                comparator
            )

        except (
            ValueError,
            TypeError
        ):

            try:

                expected = ast.unparse(
                    comparator
                )

            except Exception:

                expected = None

    return {
        "arguments": arguments,
        "expected": expected
    }


def extract_all_function_assertions(
    repository_path,
    test_file,
    function_name
):

    test_file = normalize_test_file(
        repository_path,
        test_file
    )

    if not test_file:
        return []

    full_path = os.path.join(
        repository_path,
        test_file
    )

    try:

        with open(
            full_path,
            "r",
            encoding="utf-8"
        ) as file:

            source_code = file.read()

    except (
        OSError,
        UnicodeDecodeError
    ):

        return []

    try:

        tree = ast.parse(
            source_code
        )

    except SyntaxError:

        return []

    results = []

    for test_node in ast.walk(tree):

        if not isinstance(
            test_node,
            ast.FunctionDef
        ):
            continue

        for child in ast.walk(test_node):

            if not isinstance(
                child,
                ast.Assert
            ):
                continue

            assertion_node = child.test

            assertion = ast.unparse(
                assertion_node
            )

            function_call = None

            for subnode in ast.walk(
                assertion_node
            ):

                if not isinstance(
                    subnode,
                    ast.Call
                ):
                    continue

                if not isinstance(
                    subnode.func,
                    ast.Name
                ):
                    continue

                if (
                    function_name is None
                    or subnode.func.id == function_name
                ):

                    function_call = subnode
                    break

            if function_call is None:
                continue

            call_data = extract_function_call_data(
                assertion_node,
                function_call.func.id
            )

            results.append({
                "test": test_node.name,
                "assertion": assertion,
                "arguments": call_data["arguments"],
                "expected": call_data["expected"]
            })

    return results


def extract_expected_behavior(
    repository_path,
    localized_failures
):

    behaviors = []

    for failure in localized_failures:

        test_file = normalize_test_file(
            repository_path,
            failure.get("test_file")
        )

        test_name = failure.get(
            "test_name"
        )

        function_name = failure.get(
            "function"
        )

        assertions = extract_all_function_assertions(
            repository_path,
            test_file,
            function_name
        )

        # ---------------------------------------------------------
        # Normal test failure
        # ---------------------------------------------------------
        if test_name:

            matching_assertion = None

            for assertion in assertions:

                if assertion["test"] == test_name:

                    matching_assertion = assertion
                    break

            if matching_assertion:

                behaviors.append({
                    "test_file": test_file,
                    "test_name": test_name,
                    "function": function_name,
                    "arguments": matching_assertion[
                        "arguments"
                    ],
                    "expected": matching_assertion[
                        "expected"
                    ],
                    "actual": failure.get(
                        "actual"
                    ),
                    "location": failure.get(
                        "location"
                    ),
                    "assertion": matching_assertion[
                        "assertion"
                    ]
                })

            continue

        # ---------------------------------------------------------
        # Collection / import failure
        # ---------------------------------------------------------
        for assertion in assertions:

            behaviors.append({
                "test_file": test_file,
                "test_name": assertion["test"],
                "function": function_name,
                "arguments": assertion["arguments"],
                "expected": assertion["expected"],
                "actual": None,
                "location": failure.get(
                    "location"
                ),
                "assertion": assertion["assertion"]
            })

    return behaviors
