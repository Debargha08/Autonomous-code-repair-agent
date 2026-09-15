import subprocess


def run_tests(state):

    repository_path = state["repository_path"]

    command = [
        "python3",
        "-m",
        "pytest",
        "-v"
    ]

    print(
        "\n================ TEST RUNNER ================\n"
    )

    print(
        f"Repository: {repository_path}\n"
    )

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

        print(output)

        status = (
            "tests_passed"
            if result.returncode == 0
            else "tests_failed"
        )

        print(
            "=============================================="
        )

        print(
            f"Test Status: {status}"
        )

        print(
            "==============================================\n"
        )

        return {
            "test_results": output,
            "status": status
        }

    except Exception as error:

        print(
            f"Test Runner Error: {error}"
        )

        return {
            "test_results": str(error),
            "status": "test_runner_error"
        }
