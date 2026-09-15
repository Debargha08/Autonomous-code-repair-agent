import ast


def parse_source(source_code):
    try:
        return ast.parse(source_code)
    except SyntaxError as error:
        raise ValueError(
            f"Source code contains invalid Python syntax: {error}"
        )


def find_function_node(tree, function_name):
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

    if not matches:
        return None

    if len(matches) > 1:
        raise ValueError(
            f"Multiple definitions of function "
            f"'{function_name}' found."
        )

    return matches[0]


def collect_statements(
    body,
    statements,
    depth=0,
    parent_type=None,
    path=()
):
    """
    Recursively collect every statement inside a function.

    Includes statements nested inside:

    - if
    - elif
    - else
    - for
    - while
    - try
    - except
    - finally
    - with
    - match
    - nested blocks

    Each statement receives a structural path so that it
    can later be targeted without relying only on line numbers.
    """

    for index, node in enumerate(
        body,
        start=1
    ):

        current_path = path + (index,)

        statement = {
            "index": len(statements) + 1,
            "type": type(node).__name__,
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "depth": depth,
            "parent_type": parent_type,
            "path": current_path,
            "source": ast.unparse(node),
        }

        statements.append(
            statement
        )

        child_blocks = []

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            # Nested definitions are boundaries of their own.
            # Do not treat their internal statements as part
            # of the outer function's executable body.
            continue

        for field_name in (
            "body",
            "orelse",
            "finalbody",
        ):
            field_value = getattr(
                node,
                field_name,
                None
            )

            if isinstance(
                field_value,
                list
            ):

                child_blocks.append(
                    (
                        field_name,
                        field_value
                    )
                )

        handlers = getattr(
            node,
            "handlers",
            None
        )

        if handlers:

            for handler_index, handler in enumerate(
                handlers,
                start=1
            ):

                if isinstance(
                    handler,
                    ast.ExceptHandler
                ):

                    child_blocks.append(
                        (
                            f"except_{handler_index}",
                            handler.body
                        )
                    )

        for block_name, child_body in child_blocks:

            collect_statements(
                child_body,
                statements,
                depth=depth + 1,
                parent_type=type(node).__name__,
                path=current_path + (
                    block_name,
                ),
            )


def extract_statements(function_node):
    """
    Extract every executable statement from a function,
    including nested statements.
    """

    statements = []

    collect_statements(
        function_node.body,
        statements
    )

    return statements


def localize_statements(
    source_code,
    function_name
):
    """
    Locate every statement inside a target function.

    Returns a structured description containing:

    - function boundaries
    - statement type
    - source
    - line range
    - nesting depth
    - parent statement
    - structural path
    """

    tree = parse_source(
        source_code
    )

    function_node = find_function_node(
        tree,
        function_name
    )

    if function_node is None:
        raise ValueError(
            f"Function '{function_name}' "
            "was not found."
        )

    statements = extract_statements(
        function_node
    )

    return {
        "function": function_name,
        "start_line": function_node.lineno,
        "end_line": function_node.end_lineno,
        "statements": statements,
    }
