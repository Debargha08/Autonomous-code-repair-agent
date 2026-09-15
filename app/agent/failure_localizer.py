import ast
import os
import re


def find_function_in_file(file_path, function_name):

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:
            source_code = file.read()

    except (OSError, UnicodeDecodeError):

        return None

    try:

        tree = ast.parse(source_code)

    except SyntaxError:

        return None

    for node in ast.walk(tree):

        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):

            if node.name == function_name:

                return {
                    "function": function_name,
                    "file": file_path,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "exists": True
                }

    return None


def resolve_imported_module(
    repository_path,
    error_message
):

    """
    Resolve the Python module mentioned in an ImportError
    to a source file inside the repository.
    """

    match = re.search(
        r"from ['\"]([^'\"]+)['\"]",
        error_message
    )

    if not match:

        return None

    module_name = match.group(1)

    module_parts = module_name.split(".")

    relative_path = os.path.join(
        *module_parts
    ) + ".py"

    candidate = os.path.join(
        repository_path,
        relative_path
    )

    if os.path.isfile(candidate):

        return os.path.relpath(
            candidate,
            repository_path
        )

    return None


def locate_failure(
    repository_path,
    failure
):

    function_name = failure.get("function")

    if not function_name:

        return None

    # -------------------------------------------------
    # CASE 1: SEARCH FOR AN EXISTING FUNCTION
    # -------------------------------------------------

    ignored_directories = {
        ".git",
        ".pytest_cache",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "node_modules"
    }

    for root, directories, files in os.walk(
        repository_path
    ):

        directories[:] = [
            directory
            for directory in directories
            if directory not in ignored_directories
        ]

        for file_name in files:

            if not file_name.endswith(".py"):
                continue

            file_path = os.path.join(
                root,
                file_name
            )

            result = find_function_in_file(
                file_path,
                function_name
            )

            if result:

                relative_path = os.path.relpath(
                    file_path,
                    repository_path
                )

                result["file"] = relative_path

                return result

    # -------------------------------------------------
    # CASE 2: FUNCTION DOES NOT EXIST
    # -------------------------------------------------

    if failure.get("error_type") == "ImportError":

        source_file = resolve_imported_module(
            repository_path,
            failure.get(
                "error_message",
                ""
            )
        )

        if source_file:

            return {
                "function": function_name,
                "file": source_file,
                "start_line": None,
                "end_line": None,
                "exists": False
            }

    return None


def localize_failures(
    repository_path,
    failures
):

    localized_failures = []

    for failure in failures:

        location = locate_failure(
            repository_path,
            failure
        )

        localized_failure = {
            **failure,
            "location": location
        }

        localized_failures.append(
            localized_failure
        )

    return localized_failures
