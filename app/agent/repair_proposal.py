import ast
import json
import re


SUPPORTED_REPAIR_TYPES = {
    "replace_function",
    "replace_statement",
    "insert_statement",
    "add_import",
}


EXECUTABLE_REPAIR_TYPES = {
    "replace_function",
    "replace_statement",
}


REQUIRED_FIELDS = {
    "replace_function": {
        "repair_type",
        "function",
        "code",
    },
    "replace_statement": {
        "repair_type",
        "function",
        "path",
        "code",
    },
}


ALLOWED_FIELDS = {
    "replace_function": {
        "repair_type",
        "function",
        "code",
    },
    "replace_statement": {
        "repair_type",
        "function",
        "path",
        "code",
    },
    "insert_statement": {
        "repair_type",
        "function",
        "path",
        "code",
    },
    "add_import": {
        "repair_type",
        "code",
    },
}


def parse_repair_proposal(raw_output):
    """
    Parse and validate a structured repair proposal
    returned by the repair generator.
    """

    if not isinstance(raw_output, str):
        raise ValueError(
            "Repair generator output must be a string."
        )

    raw_output = raw_output.strip()

    if not raw_output:
        raise ValueError(
            "Repair generator returned empty output."
        )

    try:
        proposal = json.loads(raw_output)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Repair generator returned invalid JSON: {error}"
        )

    return validate_repair_proposal(
        proposal
    )


def validate_function_name(function_name):
    if not isinstance(
        function_name,
        str
    ):
        raise ValueError(
            "Function name must be a string."
        )

    if not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*",
        function_name
    ):
        raise ValueError(
            f"Invalid function name: {function_name}"
        )


def validate_python_code(code):
    if not isinstance(
        code,
        str
    ):
        raise ValueError(
            "Repair code must be a string."
        )

    try:
        return ast.parse(code)
    except SyntaxError as error:
        raise ValueError(
            f"Repair code contains invalid Python syntax: {error}"
        )


def validate_exactly_one_function(
    tree,
    function_name
):
    top_level_functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    ]

    if len(top_level_functions) != 1:
        raise ValueError(
            "replace_function repair must contain "
            "exactly one top-level function."
        )

    target_function = top_level_functions[0]

    if target_function.name != function_name:
        raise ValueError(
            "Generated function name does not match "
            f"target function '{function_name}'."
        )

    if len(tree.body) != 1:
        raise ValueError(
            "replace_function repair cannot contain "
            "top-level code outside the target function."
        )


def validate_statement_code(code):
    tree = validate_python_code(
        code
    )

    if len(tree.body) != 1:
        raise ValueError(
            "replace_statement repair must contain "
            "exactly one statement."
        )

    return tree


def validate_statement_path(path):
    if not isinstance(
        path,
        list
    ):
        raise ValueError(
            "Statement path must be a list."
        )

    if not path:
        raise ValueError(
            "Statement path cannot be empty."
        )

    for component in path:

        if isinstance(
            component,
            bool
        ):
            raise ValueError(
                "Statement path cannot contain boolean values."
            )

        if isinstance(
            component,
            int
        ):
            if component < 1:
                raise ValueError(
                    "Statement path indexes must be "
                    "positive integers."
                )

        elif isinstance(
            component,
            str
        ):
            if component not in {
                "body",
                "orelse",
                "finalbody",
            } and not re.fullmatch(
                r"except_[0-9]+",
                component
            ):
                raise ValueError(
                    f"Invalid statement path component: {component}"
                )

        else:
            raise ValueError(
                "Statement path components must be "
                "positive integers or valid block names."
            )


def validate_repair_proposal(
    proposal
):
    """
    Validate a structured repair proposal.

    Supported executable repairs:

        replace_function
        replace_statement

    Future repair types remain recognized but are
    intentionally non-executable.
    """

    if isinstance(
        proposal,
        str
    ):
        try:
            proposal = json.loads(
                proposal
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Repair proposal is not valid JSON: {error}"
            )

    if not isinstance(
        proposal,
        dict
    ):
        raise ValueError(
            "Repair proposal must be a JSON object."
        )

    repair_type = proposal.get(
        "repair_type"
    )

    if repair_type not in SUPPORTED_REPAIR_TYPES:
        raise ValueError(
            f"Unsupported repair type: {repair_type}"
        )

    required_fields = REQUIRED_FIELDS.get(
        repair_type,
        set()
    )

    missing_fields = (
        required_fields
        - proposal.keys()
    )

    if missing_fields:
        raise ValueError(
            "Repair proposal is missing required "
            f"fields: {sorted(missing_fields)}"
        )

    allowed_fields = ALLOWED_FIELDS.get(
        repair_type,
        set()
    )

    unexpected_fields = (
        proposal.keys()
        - allowed_fields
    )

    if unexpected_fields:
        raise ValueError(
            "Repair proposal contains unexpected "
            f"fields: {sorted(unexpected_fields)}"
        )

    if repair_type in {
        "replace_function",
        "replace_statement",
    }:
        validate_function_name(
            proposal["function"]
        )

    if repair_type == "replace_function":

        tree = validate_python_code(
            proposal["code"]
        )

        validate_exactly_one_function(
            tree,
            proposal["function"]
        )

    elif repair_type == "replace_statement":

        validate_statement_path(
            proposal["path"]
        )

        validate_statement_code(
            proposal["code"]
        )

    elif repair_type == "insert_statement":

        validate_statement_path(
            proposal["path"]
        )

        validate_statement_code(
            proposal["code"]
        )

    elif repair_type == "add_import":

        validate_python_code(
            proposal["code"]
        )

    return {
        "valid": True,
        "repair_type": repair_type,
        "executable": (
            repair_type
            in EXECUTABLE_REPAIR_TYPES
        ),
        "proposal": proposal,
    }


def is_executable_repair(
    proposal
):
    repair_type = proposal.get(
        "repair_type"
    )

    return (
        repair_type
        in EXECUTABLE_REPAIR_TYPES
    )
