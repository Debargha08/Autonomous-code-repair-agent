import subprocess


def run_targeted_test(
    repository_path,
    test_file,
    test_name
):
    """
    Run a single failing test.

    Returns:
        {
            "test": str,
            "output": str,
            "status": str
        }
    """

    test_target = f"{test_file}::{test_name}"

    command = [
        "python3",
        "-m",
        "pytest",
        test_target,
        "-v"
    ]

    print("\n================ TARGETED TEST ================\n")

    print(f"Running: {test_target}\n")

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

        if result.returncode == 0:
            status = "targeted_test_passed"
        else:
            status = "targeted_test_failed"

        print("===============================================\n")
        print(f"Targeted Test Status: {status}")
        print("===============================================\n")

        return {
            "test": test_target,
            "output": output,
            "status": status
        }

    except Exception as error:

        print(f"Targeted Test Runner Error: {error}")

        return {
            "test": test_target,
            "output": str(error),
            "status": "targeted_test_runner_error"
        }