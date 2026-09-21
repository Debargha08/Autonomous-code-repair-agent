
import os
import shutil

from app.agent.failure_parser import parse_test_failures
from app.agent.failure_localizer import localize_failures
from app.agent.expected_behavior import extract_expected_behavior
from app.agent.statement_localizer import localize_statements
from app.agent.repair_context import build_repair_context
from app.agent.repair_generator import generate_repair
from app.agent.repair_applier import apply_repair
from app.agent.targeted_test_runner import run_targeted_test
from app.agent.regression_test_runner import (
    run_full_test_suite,
    run_regression_tests
)
from app.agent.repair_decision import decide_repair
from app.agent.reflector import reflect_on_failure
from app.tools.git_tools import (
    is_git_repository,
    create_repair_checkpoint,
    rollback_to_checkpoint,
)


MAX_RETRIES = 2


def run_repair_pipeline(
    repository_path,
    test_output,
    task
):
    """
    Complete autonomous software repair pipeline.

    Test Runner
        ↓
    Failure Parser
        ↓
    Failure Localization
        ↓
    Expected Behavior
        ↓
    Repair Context
        ↓
    Structured Repair Generator
        ↓
    Proposal Validation
        ↓
    AST Surgical Applier
        ↓
    Targeted Tests
        ↓
    Reflector
        ↓
    Retry
        ↓
    Regression Tests
        ↓
    Repair Decision
        ↓
    Accept / Rollback
    """

    print(
        "\n================ REPAIR PIPELINE ================\n"
    )

    # ==================================================
    # 1. PARSE TEST FAILURES
    # ==================================================

    print(
        "[1/9] Parsing test failures..."
    )

    failures = parse_test_failures(
        test_output
    )

    print(
        f"Detected failures: {len(failures)}"
    )

    if not failures:

        print(
            "\n✓ No test failures detected."
        )

        return {
            "status": "no_failures",
            "failures": [],
            "localized_failures": [],
            "expected_behaviors": [],
            "repair_contexts": [],
            "applied_repairs": [],
            "decisions": []
        }

    # ==================================================
    # 2. LOCALIZE FAILURES
    # ==================================================

    print(
        "\n[2/9] Localizing failures..."
    )

    localized_failures = localize_failures(
        repository_path,
        failures
    )

    print(
        f"Localized failures: "
        f"{sum(1 for failure in localized_failures if failure.get('location'))}"
    )

    # ==================================================
    # 3. EXTRACT EXPECTED BEHAVIOR
    # ==================================================

    print(
        "\n[3/9] Extracting expected behavior..."
    )

    expected_behaviors = extract_expected_behavior(
        repository_path,
        localized_failures
    )

    print(
        f"Expected behaviors: "
        f"{len(expected_behaviors)}"
    )

    # ==================================================
    # 4. BUILD REPAIR CONTEXT
    # ==================================================

    print(
        "\n[4/9] Building repair context..."
    )

    repair_contexts = build_repair_context(
        repository_path,
        localized_failures,
        expected_behaviors
    )

    # ==================================================
    # 4A. LOCALIZE TARGET FUNCTION STATEMENTS
    # ==================================================

    print(
        "\n[4A/9] Localizing target statements..."
    )

    for context in repair_contexts:

        source_file = context.get(
            "source_file"
        )

        function_name = context.get(
            "function"
        )

        if not source_file or not function_name:
            context["statements"] = []
            continue

        source_path = os.path.join(
            repository_path,
            source_file
        )

        try:
            with open(
                source_path,
                "r",
                encoding="utf-8"
            ) as file:
                source_code = file.read()
        except (OSError, UnicodeDecodeError):
            context["statements"] = []
            continue

        statement_data = localize_statements(
            source_code,
            function_name
        )

        context["statements"] = statement_data.get(
            "statements",
            []
        )

        print(
            f"Statements localized: "
            f"{len(context['statements'])}"
        )

    print(
        f"Repair contexts: "
        f"{len(repair_contexts)}"
    )

    # ==================================================
    # 5. CAPTURE FULL TEST-SUITE BASELINE
    # ==================================================

    print(
        "\n[5/9] Capturing full test-suite baseline..."
    )

    baseline_result = run_full_test_suite(
        repository_path
    )

    baseline_output = baseline_result[
        "output"
    ]

    print(
        f"Baseline failures: "
        f"{len(baseline_result['failed_tests'])}"
    )

    for failure in sorted(
        baseline_result["failed_tests"]
    ):

        print(
            f"  EXISTING: {failure}"
        )

    # ==================================================
    # 6. GENERATE AND APPLY REPAIRS
    # ==================================================

    print(
        "\n[6/9] Generating and applying repairs..."
    )

    repair_results = []

    applied_repairs = []

    for context in repair_contexts:

        source_file = context[
            "source_file"
        ]

        function_name = context[
            "function"
        ]

        # --------------------------------------------------
        # Create a Git checkpoint before modifying the
        # target source file.
        #
        # The checkpoint is path-scoped. It never resets
        # or commits the entire parent repository.
        # --------------------------------------------------

        repair_checkpoint = None

        if is_git_repository(repository_path):

            try:

                repair_checkpoint = create_repair_checkpoint(
                    repository_path,
                    target_files=[source_file],
                    message=(
                        f"repair checkpoint: "
                        f"{source_file}"
                    )
                )

                print(
                    "\n✓ Git repair checkpoint created."
                )

                print(
                    f"  Commit: "
                    f"{repair_checkpoint['commit']}"
                )

                print(
                    f"  Target: "
                    f"{source_file}"
                )

            except Exception as checkpoint_error:

                print(
                    "\n✗ Git checkpoint creation failed:"
                )

                print(
                    checkpoint_error
                )

                print(
                    "✗ Repair skipped for safety."
                )

                continue

        else:

            print(
                "\n⚠ Target is not inside a Git repository."
            )

            print(
                "⚠ Continuing with file backup safety only."
            )

        print(
            "\n--------------------------------------------------"
        )

        print(
            f"Repair target: {source_file}"
        )

        print(
            f"Function: {function_name}"
        )

        print(
            "--------------------------------------------------"
        )

        try:

            # --------------------------------------------------
            # Generate structured repair proposal.
            # --------------------------------------------------

            proposal = generate_repair(
                repository_path,
                context
            )

            # --------------------------------------------------
            # Apply only validated target function.
            # --------------------------------------------------

            result = apply_repair(
                repository_path,
                source_file,
                proposal["code"],
                function_name=proposal["function"],
                repair_type=proposal["repair_type"],
                statement_path=proposal.get("path")
            )

            repair_results.append(
                {
                    "context": context,
                    "proposal": proposal,
                    "result": result,
                    "checkpoint": repair_checkpoint
                }
            )

            if (
                result["status"]
                == "repair_applied"
            ):

                applied_repairs.append(
                    {
                        "source_file": source_file,
                        "function": function_name,
                        "repair_type": proposal[
                            "repair_type"
                        ],
                        "backup_file": result.get(
                            "backup_file"
                        ),
                        "status": "repair_applied"
                    }
                )

                print(
                    f"✓ Repair applied to "
                    f"{function_name}"
                )

            else:

                print(
                    f"✗ Repair failed: "
                    f"{result['status']}"
                )

        except Exception as error:

            print(
                "\n✗ Repair generation/application failed:"
            )

            print(
                error
            )

            # --------------------------------------------------
            # Generation/validation retry loop.
            #
            # A rejected repair proposal is itself a retryable
            # failure. Reflector feedback is regenerated after
            # every rejected attempt.
            # --------------------------------------------------

            generation_error = error
            generation_success = False

            for retry_attempt in range(1, MAX_RETRIES + 1):

                print(
                    "\n--------------------------------------------------"
                )

                print(
                    f"Generation retry {retry_attempt}/{MAX_RETRIES}"
                )

                print(
                    "--------------------------------------------------"
                )

                reflection = None

                # --------------------------------------------------
                # Reflect on the rejected repair proposal.
                # --------------------------------------------------

                try:

                    reflection_result = reflect_on_failure(
                        repository_path,
                        task,
                        context,
                        [
                            {
                                "test": "repair_generation",
                                "status": "repair_generation_failed",
                                "output": (
                                    "The generated repair was rejected "
                                    "before targeted tests could run.\n\n"
                                    f"Validation error: {generation_error}"
                                )
                            }
                        ]
                    )

                    reflection = reflection_result.get(
                        "reflection"
                    )

                except Exception as reflection_error:

                    print(
                        "\n✗ Reflector failed:"
                    )

                    print(
                        reflection_error
                    )

                    generation_error = reflection_error
                    continue

                if not reflection:

                    print(
                        "\n✗ No reflector feedback "
                        "available; retry aborted."
                    )

                    break

                # --------------------------------------------------
                # Generate improved repair using reflection.
                # --------------------------------------------------

                try:

                    print(
                        "\nRetrying repair generation "
                        "using reflector feedback..."
                    )

                    retry_proposal = generate_repair(
                        repository_path,
                        context,
                        reflection
                    )

                    retry_result = apply_repair(
                        repository_path,
                        source_file,
                        retry_proposal["code"],
                        function_name=(
                            retry_proposal["function"]
                        ),
                        repair_type=(
                            retry_proposal["repair_type"]
                        ),
                        statement_path=(
                            retry_proposal.get("path")
                        )
                    )

                    if (
                        retry_result["status"]
                        != "repair_applied"
                    ):

                        print(
                            "\n✗ Retry repair could "
                            "not be applied."
                        )

                        generation_error = (
                            f"Repair application returned "
                            f"status: {retry_result['status']}"
                        )

                        continue

                    # --------------------------------------------------
                    # Only record successfully applied repairs.
                    # --------------------------------------------------

                    repair_results.append(
                        {
                            "context": context,
                            "proposal": retry_proposal,
                            "result": retry_result,
                            "checkpoint": repair_checkpoint
                        }
                    )

                    applied_repairs.append(
                        {
                            "source_file": source_file,
                            "function": function_name,
                            "repair_type": (
                                retry_proposal[
                                    "repair_type"
                                ]
                            ),
                            "backup_file": (
                                retry_result.get(
                                    "backup_file"
                                )
                            ),
                            "status": "repair_applied"
                        }
                    )

                    generation_success = True

                    print(
                        "\n✓ Retry repair applied."
                    )

                    break

                except Exception as retry_error:

                    print(
                        "\n✗ Retry repair "
                        "generation/application failed:"
                    )

                    print(
                        retry_error
                    )

                    generation_error = retry_error

            # --------------------------------------------------
            # No valid repair was produced after all generation
            # retries.
            # --------------------------------------------------

            if not generation_success:

                print(
                    "\n✗ No valid repair was applied "
                    "for this context after generation retries."
                )

    # ==================================================
    # 7. TARGETED TESTS + REFLECTION + RETRY
    # ==================================================

    print(
        "\n[7/9] Running targeted tests..."
    )

    processed_repairs = []

    for repair in repair_results:

        context = repair[
            "context"
        ]

        source_file = context[
            "source_file"
        ]

        function_name = context[
            "function"
        ]

        result = repair.get(
            "result",
            {}
        )

        if (
            result.get("status")
            != "repair_applied"
        ):

            continue

        current_repair = repair

        successful = False

        attempts = 0

        last_targeted_result = None

        while attempts <= MAX_RETRIES:

            attempts += 1

            print(
                "\n=================================================="
            )

            print(
                f"Repair attempt {attempts}"
            )

            print(
                f"Function: {function_name}"
            )

            print(
                "=================================================="
            )

            # --------------------------------------------------
            # Run every affected test individually.
            # --------------------------------------------------

            targeted_results = []

            for behavior in context.get(
                "behaviors",
                []
            ):

                test_file = behavior.get(
                    "test_file"
                )

                test_name = behavior.get(
                    "test_name"
                )

                if not test_file or not test_name:
                    continue

                print(
                    f"\nRunning targeted test: "
                    f"{test_file}::{test_name}"
                )

                targeted_test_result = (
                    run_targeted_test(
                        repository_path,
                        test_file,
                        test_name
                    )
                )

                targeted_results.append(
                    targeted_test_result
                )

            # --------------------------------------------------
            # Aggregate targeted results.
            # --------------------------------------------------

            targeted_output_parts = []

            all_passed = True

            for targeted_test_result in targeted_results:

                targeted_output_parts.append(
                    targeted_test_result.get(
                        "output",
                        ""
                    )
                )

                if (
                    targeted_test_result.get(
                        "status"
                    )
                    != "targeted_test_passed"
                ):

                    all_passed = False

            test_output = "\n".join(
                targeted_output_parts
            )

            targeted_status = (
                "targeted_test_passed"
                if all_passed
                else "targeted_test_failed"
            )

            targeted_result = {
                "status": targeted_status,
                "output": test_output,
                "results": targeted_results
            }

            last_targeted_result = targeted_result

            print(
                f"\nTargeted tests executed: "
                f"{len(targeted_results)}"
            )

            print(
                f"Targeted Test Status: "
                f"{targeted_status}"
            )

            # --------------------------------------------------
            # Targeted tests passed.
            # --------------------------------------------------

            if all_passed:

                print(
                    "\n✓ TARGETED TESTS PASSED"
                )

                successful = True

                processed_repairs.append(
                    {
                        **current_repair,
                        "attempts": attempts,
                        "targeted_status": targeted_status,
                        "targeted_output": test_output
                    }
                )

                break

            # --------------------------------------------------
            # Targeted tests failed.
            # --------------------------------------------------

            print(
                "\n✗ TARGETED TESTS FAILED"
            )

            # --------------------------------------------------
            # Maximum retry reached.
            # --------------------------------------------------

            if attempts > MAX_RETRIES:

                print(
                    "\n✗ Maximum repair attempts reached."
                )

                processed_repairs.append(
                    {
                        **current_repair,
                        "attempts": attempts,
                        "targeted_status": targeted_status,
                        "targeted_output": test_output
                    }
                )

                break

            # --------------------------------------------------
            # Reflect on failed repair.
            # --------------------------------------------------

            try:

                reflection_result = reflect_on_failure(
                    repository_path,
                    task,
                    context,
                    [targeted_result]
                )

                reflection = reflection_result.get(
                    "reflection"
                )

            except Exception as error:

                print(
                    "\n✗ Reflector failed:"
                )

                print(
                    error
                )

                reflection = None

            # --------------------------------------------------
            # Generate improved repair.
            # --------------------------------------------------

            try:

                proposal = generate_repair(
                    repository_path,
                    context,
                    reflection
                )

                retry_result = apply_repair(
                    repository_path,
                    source_file,
                    proposal["code"],
                    function_name=proposal["function"],
                    repair_type=proposal["repair_type"],
                    statement_path=proposal.get("path")
                )

                if (
                    retry_result["status"]
                    != "repair_applied"
                ):

                    print(
                        "\n✗ Retry repair could not be applied."
                    )

                    continue

                current_repair = {
                    "context": context,
                    "proposal": proposal,
                    "result": retry_result,
                    "checkpoint": current_repair.get(
                        "checkpoint"
                    )
                }

                print(
                    "\n✓ Retry repair applied."
                )

            except Exception as error:

                print(
                    "\n✗ Retry repair generation failed:"
                )

                print(
                    error
                )

        # --------------------------------------------------
        # Safety fallback.
        # --------------------------------------------------

        if not any(
            item.get("context") is context
            for item in processed_repairs
        ):

            processed_repairs.append(
                {
                    **current_repair,
                    "attempts": attempts,
                    "targeted_status": (
                        "targeted_test_passed"
                        if successful
                        else "targeted_test_failed"
                    ),
                    "targeted_output": (
                        last_targeted_result.get(
                            "output",
                            ""
                        )
                        if last_targeted_result
                        else ""
                    )
                }
            )

    # ==================================================
    # 8. REGRESSION TESTS
    # ==================================================

    print(
        "\n[8/9] Running regression tests..."
    )

    latest_target_output = ""

    for repair in processed_repairs:

        if repair.get(
            "targeted_output"
        ):

            latest_target_output = repair[
                "targeted_output"
            ]

    if not latest_target_output:

        latest_target_output = test_output

    regression_result = run_regression_tests(
        repository_path,
        baseline_output,
        latest_target_output
    )

    regression_status = regression_result[
        "status"
    ]

    # ==================================================
    # 9. FINAL DECISION
    # ==================================================

    print(
        "\n[9/9] Evaluating and finalizing pipeline..."
    )

    final_decisions = []

    accepted_repairs = []

    rolled_back_repairs = []

    for repair in processed_repairs:

        context = repair[
            "context"
        ]

        source_file = context[
            "source_file"
        ]

        targeted_status = repair.get(
            "targeted_status"
        )

        apply_result = repair.get(
            "result",
            {}
        )

        backup_file = apply_result.get(
            "backup_file"
        )

        print(
            "\n--------------------------------------------------"
        )

        print(
            f"Evaluating repair: {source_file}"
        )

        print(
            f"Targeted status: {targeted_status}"
        )

        print(
            f"Regression status: {regression_status}"
        )

        print(
            "--------------------------------------------------"
        )

        # --------------------------------------------------
        # IMPORTANT:
        #
        # decide_repair() expects:
        #
        # repository_path
        # source_file
        # backup_file
        # targeted_test_status
        # regression_test_status
        # --------------------------------------------------

        decision = decide_repair(
            repository_path,
            source_file,
            backup_file,
            targeted_status,
            regression_status
        )

        final_decisions.append(
            decision
        )

        # --------------------------------------------------
        # Normalize decision result.
        #
        # Supports either:
        #
        # "accept"
        #
        # or:
        #
        # {"decision": "accept"}
        # --------------------------------------------------

        if isinstance(
            decision,
            dict
        ):

            decision_value = decision.get(
                "decision",
                decision.get(
                    "status"
                )
            )

        else:

            decision_value = decision

        if decision_value in ("accept", "accepted", "repair_accepted"):

            accepted_repairs.append(
                source_file
            )

            print(
                f"✓ REPAIR ACCEPTED: "
                f"{source_file}"
            )

        else:

            rolled_back_repairs.append(
                source_file
            )

            print(
                f"✗ REPAIR REJECTED: "
                f"{source_file}"
            )

    # ==================================================
    # FINALIZATION
    # ==================================================

    print(
        "\n================ FINALIZATION ================\n"
    )

    # --------------------------------------------------
    # Remove backups for accepted repairs.
    # --------------------------------------------------

    for source_file in accepted_repairs:

        backup_file = os.path.join(
            repository_path,
            source_file + ".bak"
        )

        try:

            if os.path.exists(
                backup_file
            ):

                os.remove(
                    backup_file
                )

                print(
                    f"✓ Removed backup: "
                    f"{source_file}.bak"
                )

        except OSError as error:

            print(
                f"⚠ Could not remove backup "
                f"{source_file}.bak: {error}"
            )

    # --------------------------------------------------
    # Roll back rejected repairs using the Git checkpoint.
    # --------------------------------------------------

    for repair in processed_repairs:

        context = repair[
            "context"
        ]

        source_file = context[
            "source_file"
        ]

        if source_file not in rolled_back_repairs:
            continue

        checkpoint = repair.get(
            "checkpoint"
        )

        try:

            if checkpoint:

                rollback_to_checkpoint(
                    repository_path,
                    checkpoint
                )

                print(
                    f"✓ Git rollback completed: "
                    f"{source_file}"
                )

                # Remove the legacy file backup after the
                # Git checkpoint has successfully restored
                # the target file.
                backup_file = os.path.join(
                    repository_path,
                    source_file + ".bak"
                )

                if os.path.exists(
                    backup_file
                ):

                    os.remove(
                        backup_file
                    )

                    print(
                        f"✓ Removed backup: "
                        f"{source_file}.bak"
                    )

            else:

                print(
                    f"⚠ No Git checkpoint available "
                    f"for {source_file}; "
                    f"repair was not automatically rolled back."
                )

        except Exception as error:

            print(
                f"✗ Git rollback failed for "
                f"{source_file}: {error}"
            )

    # ==================================================
    # FINAL STATUS
    # ==================================================

    if rolled_back_repairs:

        final_status = (
            "repair_rolled_back"
        )

    elif accepted_repairs:

        final_status = (
            "repair_accepted"
        )

    else:

        final_status = (
            "repair_failed"
        )

    print(
        f"\nFinal pipeline status: "
        f"{final_status}"
    )

    print(
        "\n================================================\n"
    )

    return {
        "status": final_status,
        "failures": failures,
        "localized_failures": localized_failures,
        "expected_behaviors": expected_behaviors,
        "repair_contexts": repair_contexts,
        "applied_repairs": applied_repairs,
        "processed_repairs": processed_repairs,
        "decisions": final_decisions,
        "regression_result": regression_result
    }

