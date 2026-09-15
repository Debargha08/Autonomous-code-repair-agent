from app.agent.failure_parser import parse_test_failures
from app.agent.failure_localizer import localize_failures
from app.agent.expected_behavior import extract_expected_behavior
from app.agent.repair_context import build_repair_context
from app.agent.repair_generator import generate_repair
from app.agent.repair_applier import apply_repair
from app.agent.targeted_test_runner import run_targeted_test
from app.agent.regression_test_runner import run_regression_tests
from app.agent.repair_decision import decide_repair


def run_repair_pipeline(
    repository_path,
    test_output
):
    """
    Execute the autonomous test-driven repair pipeline.

    Pipeline:

        Test Failure
             ↓
        Failure Parser
             ↓
        Failure Localization
             ↓
        Expected Behavior
             ↓
        Repair Context
             ↓
        Repair Generator
             ↓
        Repair Applier
             ↓
        Targeted Test
             ↓
        Regression Tests
             ↓
        Accept / Rollback
    """

    print("\n")
    print("====================================================")
    print("           AUTONOMOUS REPAIR PIPELINE")
    print("====================================================")

    # ------------------------------------------------
    # STEP 1 — Parse failures
    # ------------------------------------------------

    print("\n[1/9] Parsing test failures...")

    failures = parse_test_failures(
        test_output
    )

    if not failures:

        print("No test failures detected.")

        return {
            "status": "no_failures",
            "failures": [],
            "repair_contexts": [],
            "changes": [],
            "decision": None
        }

    print(
        f"Detected {len(failures)} failure(s)."
    )

    # ------------------------------------------------
    # STEP 2 — Localize failures
    # ------------------------------------------------

    print("\n[2/9] Localizing failures...")

    localized_failures = localize_failures(
        repository_path,
        failures
    )

    # ------------------------------------------------
    # STEP 3 — Extract expected behavior
    # ------------------------------------------------

    print("\n[3/9] Extracting expected behavior...")

    expected_behaviors = extract_expected_behavior(
        repository_path,
        localized_failures
    )

    # ------------------------------------------------
    # STEP 4 — Build repair context
    # ------------------------------------------------

    print("\n[4/9] Building repair context...")

    repair_contexts = build_repair_context(
        repository_path,
        localized_failures,
        expected_behaviors
    )

    if not repair_contexts:

        print("Could not build repair context.")

        return {
            "status": "repair_context_failed",
            "failures": failures,
            "repair_contexts": [],
            "changes": [],
            "decision": None
        }

    # ------------------------------------------------
    # STEP 5 — Generate and apply repair
    # ------------------------------------------------

    print("\n[5/9] Generating and applying repair...")

    changes = []

    applied_repairs = []

    for context in repair_contexts:

        source_file = context.get(
            "source_file"
        )

        if not source_file:

            print(
                "Skipping failure without source file."
            )

            continue

        repaired_code = generate_repair(
            repository_path,
            context
        )

        repair_result = apply_repair(
            repository_path,
            source_file,
            repaired_code
        )

        print(
            f"Repair result: {repair_result['status']}"
        )

        if repair_result["status"] != "repair_applied":

            continue

        changes.append(
            source_file
        )

        applied_repairs.append(
            {
                "context": context,
                "source_file": source_file,
                "backup_file": repair_result["backup_file"]
            }
        )

    if not applied_repairs:

        return {
            "status": "repair_application_failed",
            "failures": failures,
            "repair_contexts": repair_contexts,
            "changes": changes,
            "decision": None
        }

    # ------------------------------------------------
    # STEP 6 — Targeted tests
    # ------------------------------------------------

    print("\n[6/9] Running targeted tests...")

    targeted_results = []

    for repair in applied_repairs:

        context = repair["context"]

        targeted_result = run_targeted_test(
            repository_path,
            context["test_file"],
            context["test_name"]
        )

        targeted_results.append(
            targeted_result
        )

    targeted_failed = any(
        result["status"] != "targeted_test_passed"
        for result in targeted_results
    )

    # ------------------------------------------------
    # STEP 7 — Regression tests
    # ------------------------------------------------

    if targeted_failed:

        print(
            "\nTargeted test failed."
        )

        regression_result = {
            "output": "",
            "status": "regression_tests_skipped"
        }

    else:

        print("\n[7/9] Running regression tests...")

        regression_result = run_regression_tests(
            repository_path
        )

    # ------------------------------------------------
    # STEP 8 — Decision
    # ------------------------------------------------

    print("\n[8/9] Evaluating repair...")

    final_decision = None

    for repair in applied_repairs:

        targeted_status = "targeted_test_failed"

        for result in targeted_results:

            if result["test"].endswith(
                f"::{repair['context']['test_name']}"
            ):

                targeted_status = result["status"]

                break

        decision_result = decide_repair(
            repository_path,
            repair["source_file"],
            repair["backup_file"],
            targeted_status,
            regression_result["status"]
        )

        final_decision = decision_result

    # ------------------------------------------------
    # STEP 9 — Final result
    # ------------------------------------------------

    print("\n[9/9] Finalizing pipeline...")

    if final_decision:

        final_status = final_decision["status"]

    else:

        final_status = "repair_failed"

    print("\n====================================================")
    print("              PIPELINE COMPLETE")
    print("====================================================")

    print(
        f"Final Status: {final_status}"
    )

    print("====================================================\n")

    return {
        "status": final_status,
        "failures": failures,
        "localized_failures": localized_failures,
        "expected_behaviors": expected_behaviors,
        "repair_contexts": repair_contexts,
        "changes": changes,
        "targeted_results": targeted_results,
        "regression_result": regression_result,
        "decision": final_decision
    }