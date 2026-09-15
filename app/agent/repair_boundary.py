import ast


def parse_source(source_code):
    try:
        return ast.parse(source_code)
    except SyntaxError as error:
        raise ValueError(
            f"Source code contains invalid Python syntax: {error}"
        )


def find_target_function(tree, function_name):
    matches = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            if node.name == function_name:
                matches.append(node)

    if len(matches) == 0:
        raise ValueError(
            f"Target function '{function_name}' "
            "was not found."
        )

    if len(matches) > 1:
        raise ValueError(
            f"Multiple definitions of target function "
            f"'{function_name}' were found."
        )

    return matches[0]


def normalize_node(node):
    """
    Return an AST representation that can be compared
    independently of source formatting and line numbers.
    """

    normalized = ast.fix_missing_locations(
        ast.parse(
            ast.unparse(node)
        )
    )

    return ast.dump(
        normalized,
        annotate_fields=True,
        include_attributes=False
    )


def validate_repair_boundary(
    original_source,
    repaired_function_code,
    function_name
):
    """
    Verify that a proposed function replacement stays
    strictly inside the requested repair boundary.

    The repaired proposal must contain exactly one
    top-level function and that function must have the
    requested name.

    The original source must contain exactly one
    target function.

    Returns a validation result dictionary.
    """

    if not isinstance(original_source, str):
        raise ValueError(
            "Original source must be a string."
        )

    if not isinstance(repaired_function_code, str):
        raise ValueError(
            "Repaired function code must be a string."
        )

    if not function_name:
        raise ValueError(
            "Function name must be provided."
        )

    original_tree = parse_source(
        original_source
    )

    repaired_tree = parse_source(
        repaired_function_code
    )

    original_target = find_target_function(
        original_tree,
        function_name
    )

    repaired_functions = [
        node
        for node in repaired_tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    ]

    if len(repaired_functions) != 1:
        raise ValueError(
            "Repair boundary violation: repaired code "
            "must contain exactly one top-level "
            "function definition."
        )

    repaired_target = repaired_functions[0]

    if repaired_target.name != function_name:
        raise ValueError(
            "Repair boundary violation: repaired function "
            f"'{repaired_target.name}' does not match "
            f"target '{function_name}'."
        )

    for node in repaired_tree.body:
        if node is repaired_target:
            continue

        raise ValueError(
            "Repair boundary violation: repaired proposal "
            "contains top-level code outside the target "
            "function."
        )

    original_dump = normalize_node(
        original_target
    )

    repaired_dump = normalize_node(
        repaired_target
    )

    changed = (
        original_dump != repaired_dump
    )

    return {
        "valid": True,
        "function": function_name,
        "changed": changed,
        "original_function": original_target.name,
        "repaired_function": repaired_target.name
    }
