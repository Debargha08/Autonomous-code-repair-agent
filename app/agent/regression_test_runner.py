import re
import subprocess


def extract_failed_tests(output):
    """
    Extract pytest node IDs for failed tests.

    Example:
        repair_bench/foo/tests/test_x.py::test_example
    """

    failed_tests = set()

    for line in output.splitlines():

        match = re.match(
            r"^FAILED\s+(.+::test_[A-Za-z0-9_]+)(?:\s|$)",
            line.strip()
        )

        if match:
            failed_tests.add(
                match.group(1)
            )

    return failed_tests


def run_full_test_suite(repository_path):
    """
    Run the complete pytest suite.

    Returns:
        {
            "output": str,
            "failed_tests": set,
            "returncode": int
        }
    """

    command = [
        "python3",
        "-m",
        "pytest",
        "-v"
    ]

    try:

        result = subprocess.run(
            command,
            cwd=repository_path,
            capture_output=True,
            text=True
        )

        output = (
            result.stdout
            + "\n"
            + result.stderr
        )

        return {
            "output": output,
            "failed_tests": extract_failed_tests(
                output
            ),
            "returncode": result.returncode
        }

    except Exception as error:

        return {
            "output": str(error),
            "failed_tests": set(),
            "returncode": -1
        }


def run_regression_tests(
    repository_path,
    baseline_output,
    target_output
):
    """
    Run the complete test suite after repair
    and compare failures against the baseline.

    Existing failures are tolerated.

    New failures are treated as regressions.

    Returns:
        {
            "output": str,
            "status": str,
            "baseline_failures": list,
            "current_failures": list,
            "new_failures": list
        }
    """

    print(
        "\n================ REGRESSION TESTS ================\n"
    )

    print(
        "Running complete test suite after repair...\n"
    )

    baseline_failures = extract_failed_tests(
        baseline_output
    )

    target_failures = extract_failed_tests(
        target_output
    )

    result = run_full_test_suite(
        repository_path
    )

    output = result["output"]

    current_failures = result[
        "failed_tests"
    ]

    unrelated_baseline_failures = (
        baseline_failures
        - target_failures
    )

    new_failures = (
        current_failures
        - unrelated_baseline_failures
    )

    print(output)

    print(
        "\n---------------- REGRESSION ANALYSIS ----------------"
    )

    print(
        f"\nBaseline failures: "
        f"{len(baseline_failures)}"
    )

    for failure in sorted(
        baseline_failures
    ):
        print(
            f"  BASELINE: {failure}"
        )

    print(
        f"\nTarget failures: "
        f"{len(target_failures)}"
    )

    for failure in sorted(
        target_failures
    ):
        print(
            f"  TARGET: {failure}"
        )

    print(
        f"\nUnrelated baseline failures: "
        f"{len(unrelated_baseline_failures)}"
    )

    for failure in sorted(
        unrelated_baseline_failures
    ):
        print(
            f"  PRE-EXISTING: {failure}"
        )

    print(
        f"\nCurrent failures: "
        f"{len(current_failures)}"
    )

    for failure in sorted(
        current_failures
    ):
        print(
            f"  CURRENT: {failure}"
        )

    print(
        f"\nNew failures: "
        f"{len(new_failures)}"
    )

    for failure in sorted(
        new_failures
    ):
        print(
            f"  NEW REGRESSION: {failure}"
        )

    print(
        "\n----------------------------------------------------"
    )

    if result["returncode"] == -1:

        status = (
            "regression_test_runner_error"
        )

    elif new_failures:

        status = (
            "regression_tests_failed"
        )

        print(
            "\n✗ NEW REGRESSIONS DETECTED"
        )

    else:

        status = (
            "regression_tests_passed"
        )

        print(
            "\n✓ NO NEW REGRESSIONS"
        )

    print(
        "\n===================================================\n"
    )

    print(
        f"Regression Test Status: {status}"
    )

    print(
        "===================================================\n"
    )

    return {
        "output": output,
        "status": status,
        "baseline_failures": sorted(
            baseline_failures
        ),
        "current_failures": sorted(
            current_failures
        ),
        "new_failures": sorted(
            new_failures
        )
    }
