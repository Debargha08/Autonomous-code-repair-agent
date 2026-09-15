import ast
import os
import shutil

from app.agent.repair_boundary import (
    validate_repair_boundary
)

from app.agent.statement_replacer import (
    replace_statement_in_source
)


def find_function_node(
    source_code,
    function_name
):
    """
    Find a function definition in Python source.

    Returns:
        ast.FunctionDef / ast.AsyncFunctionDef
        or None
    """

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return None

    for node in ast.walk(tree):

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef
            )
        ):

            if node.name == function_name:
                return node

    return None


def validate_python_source(
    source_code
):
    """
    Validate that the supplied source is syntactically valid Python.
    """

    try:
        ast.parse(source_code)
        return True

    except SyntaxError:
        return False


def replace_function_in_source(
    original_source,
    repaired_source,
    function_name
):
    """
    Safely extract the repaired target function from the
    generated source and replace only the corresponding
    function in the original source.

    The repair boundary is validated before modification.

    Returns:
        Modified source code.

    Raises:
        ValueError if either source is invalid or the repair
        violates the target boundary.
    """

    if not validate_python_source(
        original_source
    ):
        raise ValueError(
            "Original source contains invalid Python syntax."
        )

    if not validate_python_source(
        repaired_source
    ):
        raise ValueError(
            "Generated repair contains invalid Python syntax."
        )

    # ----------------------------------------------------
    # Validate repair boundary BEFORE applying anything.
    # ----------------------------------------------------

    boundary_result = validate_repair_boundary(
        original_source,
        repaired_source,
        function_name
    )

    if not boundary_result["valid"]:
        raise ValueError(
            "Repair boundary validation failed."
        )

    original_node = find_function_node(
        original_source,
        function_name
    )

    if original_node is None:
        raise ValueError(
            f"Target function '{function_name}' "
            "was not found in original source."
        )

    repaired_node = find_function_node(
        repaired_source,
        function_name
    )

    if repaired_node is None:
        raise ValueError(
            f"Target function '{function_name}' "
            "was not found in generated repair."
        )

    original_lines = (
        original_source.splitlines(
            keepends=True
        )
    )

    repaired_lines = (
        repaired_source.splitlines(
            keepends=True
        )
    )

    original_start = (
        original_node.lineno - 1
    )

    original_end = (
        original_node.end_lineno
    )

    repaired_start = (
        repaired_node.lineno - 1
    )

    repaired_end = (
        repaired_node.end_lineno
    )

    repaired_function = (
        repaired_lines[
            repaired_start:repaired_end
        ]
    )

    modified_lines = (
        original_lines[:original_start]
        + repaired_function
        + original_lines[original_end:]
    )

    modified_source = "".join(
        modified_lines
    )

    if not validate_python_source(
        modified_source
    ):
        raise ValueError(
            "Function replacement produced "
            "invalid Python syntax."
        )

    return modified_source


def apply_repair(
    repository_path,
    source_file,
    repaired_code,
    function_name=None,
    repair_type="replace_function",
    statement_path=None
):
    """
    Apply a validated repair to a source file.

    Supported executable repair types:

        replace_function
        replace_statement

    The repair is fully validated before the original
    source file is backed up or modified.
    """

    full_path = os.path.join(
        repository_path,
        source_file
    )

    if not os.path.isfile(
        full_path
    ):
        return {
            "source_file": source_file,
            "backup_file": None,
            "status": "target_file_not_found"
        }

    try:

        # ------------------------------------------------
        # Read original source
        # ------------------------------------------------

        with open(
            full_path,
            "r",
            encoding="utf-8"
        ) as file:

            original_source = file.read()

        # ------------------------------------------------
        # Prepare and validate repair BEFORE backup.
        # ------------------------------------------------

        if repair_type == "replace_function":

            if not function_name:
                raise ValueError(
                    "Function name is required for "
                    "replace_function."
                )

            repaired_source = (
                replace_function_in_source(
                    original_source,
                    repaired_code,
                    function_name
                )
            )

            print(
                f"✓ Boundary validation passed for "
                f"function: {function_name}"
            )

        elif repair_type == "replace_statement":

            if not function_name:
                raise ValueError(
                    "Function name is required for "
                    "replace_statement."
                )

            if statement_path is None:
                raise ValueError(
                    "Statement path is required for "
                    "replace_statement."
                )

            repaired_source = (
                replace_statement_in_source(
                    original_source,
                    repaired_code,
                    function_name,
                    statement_path
                )
            )

            print(
                f"✓ Statement replacement validated for "
                f"function: {function_name}"
            )

        else:

            raise ValueError(
                f"Unsupported executable repair type: "
                f"{repair_type}"
            )

        # ------------------------------------------------
        # Create backup ONLY after validation succeeds.
        # ------------------------------------------------

        backup_file = (
            full_path + ".bak"
        )

        if not os.path.exists(
            backup_file
        ):

            shutil.copy2(
                full_path,
                backup_file
            )

            print(
                f"✓ Created original backup: "
                f"{os.path.relpath(backup_file, repository_path)}"
            )

        else:

            print(
                "✓ Preserving original backup."
            )

        # ------------------------------------------------
        # Write repaired source
        # ------------------------------------------------

        with open(
            full_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(
                repaired_source
            )

        print(
            f"✓ Repair written to: "
            f"{os.path.relpath(full_path, repository_path)}"
        )

        return {
            "source_file": source_file,
            "backup_file": backup_file,
            "status": "repair_applied",
            "repair_type": repair_type
        }

    except (
        OSError,
        ValueError,
        SyntaxError
    ) as error:

        print(
            f"✗ Repair application failed: {error}"
        )

        return {
            "source_file": source_file,
            "backup_file": None,
            "status": "repair_application_failed",
            "error": str(error)
        }

