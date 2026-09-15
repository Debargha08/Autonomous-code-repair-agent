import os

from app.agent.statement_localizer import (
    localize_statements
)


def normalize_test_file(
    repository_path,
    test_file
):

    if not test_file:
        return None

    test_file = os.path.normpath(
        test_file
    )

    repository_path = os.path.normpath(
        repository_path
    )

    repository_name = os.path.basename(
        repository_path
    )

    prefix = repository_name + os.sep

    if test_file.startswith(prefix):
        test_file = test_file[
            len(prefix):
        ]

    return test_file


def build_repair_context(
    repository_path,
    localized_failures,
    expected_behaviors
):

    contexts_by_source = {}

    for failure in localized_failures:

        location = failure.get(
            "location"
        ) or {}

        source_file = location.get(
            "file"
        )

        function_name = failure.get(
            "function"
        )

        if not source_file:
            continue

        # ---------------------------------------------------------
        # One repair context per source file + function
        # ---------------------------------------------------------
        context_key = (
            source_file,
            function_name
        )

        if context_key not in contexts_by_source:

            source_path = os.path.join(
                repository_path,
                source_file
            )

            try:
                with open(
                    source_path,
                    "r",
                    encoding="utf-8"
                ) as source_file_handle:
                    source_code = source_file_handle.read()
            except (OSError, UnicodeDecodeError):
                source_code = ""

            statement_data = localize_statements(
                source_code,
                function_name
            )

            statements = (
                statement_data.get("statements", [])
                if isinstance(statement_data, dict)
                else []
            )

            contexts_by_source[context_key] = {
                "test_file": normalize_test_file(
                    repository_path,
                    failure.get("test_file")
                ),
                "function": function_name,
                "source_file": source_file,
                "start_line": location.get(
                    "start_line"
                ),
                "end_line": location.get(
                    "end_line"
                ),
                "statements": statements,
                "exists": location.get(
                    "exists"
                ),
                "error_type": failure.get(
                    "error_type"
                ),
                "error_message": failure.get(
                    "error_message"
                ),
                "behaviors": []
            }

    # -------------------------------------------------------------
    # Attach each behavior to the correct source/function context
    # -------------------------------------------------------------
    for behavior in expected_behaviors:

        location = behavior.get(
            "location"
        ) or {}

        source_file = location.get(
            "file"
        )

        function_name = behavior.get(
            "function"
        )

        context_key = (
            source_file,
            function_name
        )

        context = contexts_by_source.get(
            context_key
        )

        if context is None:
            continue

        behavior_test_file = normalize_test_file(
            repository_path,
            behavior.get("test_file")
        )

        behavior_copy = dict(
            behavior
        )

        behavior_copy[
            "test_file"
        ] = behavior_test_file

        context[
            "behaviors"
        ].append(
            behavior_copy
        )

    return list(
        contexts_by_source.values()
    )
