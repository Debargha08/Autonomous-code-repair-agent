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
        raise ValueError(
            f"Function '{function_name}' was not found."
        )

    if len(matches) > 1:
        raise ValueError(
            f"Multiple definitions of function "
            f"'{function_name}' were found."
        )

    return matches[0]


def validate_replacement_statement(
    replacement_code
):
    """
    Ensure the generated replacement contains
    exactly one statement and no extra top-level code.
    """

    try:
        tree = ast.parse(
            replacement_code
        )
    except SyntaxError as error:
        raise ValueError(
            f"Replacement contains invalid Python syntax: {error}"
        )

    if len(tree.body) != 1:
        raise ValueError(
            "Statement replacement must contain "
            "exactly one statement."
        )

    return tree.body[0]


def get_child_blocks(node):
    """
    Return nested statement blocks while preserving
    their structural names.
    """

    blocks = []

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
            blocks.append(
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
                blocks.append(
                    (
                        f"except_{handler_index}",
                        handler.body
                    )
                )

    return blocks


def find_statement_by_path(
    function_node,
    target_path
):
    """
    Locate a statement using the structural path
    produced by statement_localizer.py.

    Example:

        (1, 'body', 2, 'body', 1)
    """

    if not isinstance(
        target_path,
        (tuple, list)
    ):
        raise ValueError(
            "Statement path must be a tuple or list."
        )

    if not target_path:
        raise ValueError(
            "Statement path cannot be empty."
        )

    body = function_node.body
    parent = function_node
    parent_list = function_node.body
    statement_index = None

    position = 0

    while position < len(target_path):

        index = target_path[position]

        if not isinstance(
            index,
            int
        ):
            raise ValueError(
                "Statement path contains an invalid statement index."
            )

        if index < 1 or index > len(body):
            raise ValueError(
                f"Statement path index {index} "
                "is out of range."
            )

        statement_index = index - 1
        node = body[statement_index]

        if position + 1 == len(target_path):
            return {
                "node": node,
                "parent": parent,
                "parent_list": parent_list,
                "index": statement_index,
            }

        position += 1

        if position >= len(target_path):
            break

        block_name = target_path[position]

        child_blocks = dict(
            get_child_blocks(node)
        )

        if block_name not in child_blocks:
            raise ValueError(
                f"Statement path block "
                f"'{block_name}' was not found."
            )

        parent = node
        parent_list = child_blocks[block_name]

        body = child_blocks[block_name]

        position += 1

    raise ValueError(
        "Invalid statement path."
    )


def replace_statement_in_source(
    original_source,
    replacement_code,
    function_name,
    target_path
):
    """
    Replace exactly one statement inside a target function.

    The replacement itself must contain exactly one statement.
    """

    if not isinstance(
        original_source,
        str
    ):
        raise ValueError(
            "Original source must be a string."
        )

    if not isinstance(
        replacement_code,
        str
    ):
        raise ValueError(
            "Replacement code must be a string."
        )

    if not function_name:
        raise ValueError(
            "Function name must be provided."
        )

    tree = parse_source(
        original_source
    )

    function_node = find_function_node(
        tree,
        function_name
    )

    replacement_node = validate_replacement_statement(
        replacement_code
    )

    target = find_statement_by_path(
        function_node,
        target_path
    )

    target["parent_list"][
        target["index"]
    ] = replacement_node

    ast.fix_missing_locations(
        tree
    )

    modified_source = ast.unparse(
        tree
    )

    # Final syntax validation.
    parse_source(
        modified_source
    )

    return modified_source
