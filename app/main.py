import argparse
import subprocess
import sys

from app.agent.repair_agent import run_repair_pipeline


def run_tests(repository_path, tests_path=None):
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-v"
    ]

    if tests_path:
        command.append(tests_path)

    print(
        "\n================ INITIAL TEST RUN ================\n"
    )

    print(
        "Repository:",
        repository_path
    )

    if tests_path:
        print(
            "Tests:",
            tests_path
        )
    else:
        print(
            "Tests: entire repository"
        )

    print()

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

    print(output)

    print(
        "===================================================\n"
    )

    return output


def main():

    parser = argparse.ArgumentParser(
        description="Autonomous software repair agent."
    )

    parser.add_argument(
        "--repository",
        required=True,
        help="Repository path to repair."
    )

    parser.add_argument(
        "--tests",
        required=False,
        help="Test file or test directory to run."
    )

    parser.add_argument(
        "--task",
        required=False,
        default="Find and fix the failing source code.",
        help="Description of the repair task."
    )

    args = parser.parse_args()

    test_output = run_tests(
        args.repository,
        args.tests
    )

    result = run_repair_pipeline(
        repository_path=args.repository,
        test_output=test_output,
        task=args.task
    )

    print(
        "\n================ FINAL RESULT ================\n"
    )

    print(
        "Final Status:",
        result.get("status")
    )

    print(
        "\nDetected Failures:",
        len(result.get("failures", []))
    )

    print(
        "Localized Failures:",
        len(result.get("localized_failures", []))
    )

    print(
        "Expected Behaviors:",
        len(result.get("expected_behaviors", []))
    )

    print(
        "Repair Contexts:",
        len(result.get("repair_contexts", []))
    )

    print(
        "Applied Repairs:",
        len(result.get("applied_repairs", []))
    )

    print(
        "Decisions:",
        len(result.get("decisions", []))
    )

    print(
        "\n================================================\n"
    )


if __name__ == "__main__":
    main()
