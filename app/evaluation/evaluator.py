from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = PROJECT_ROOT / "sandbox" / "repair_bench"
RESULTS_FILE = PROJECT_ROOT / "app" / "evaluation" / "results.json"
REPORT_FILE = PROJECT_ROOT / "app" / "evaluation" / "report.md"


@dataclass
class BenchmarkResult:
    name: str
    path: str
    test_file: str

    baseline_passed: bool
    baseline_failures: int

    final_status: str
    detected_failures: int
    localized_failures: int
    expected_behaviors: int
    repair_contexts: int
    applied_repairs: int
    decisions: int

    repair_attempts: int
    first_attempt_successes: int
    retry_assisted_successes: int

    repair_accepted: bool
    regression_free: bool

    elapsed_seconds: float
    error: str | None = None


def run_command(
    command: list[str],
    cwd: Path,
    timeout: int = 900,
) -> tuple[int, str, float]:
    start = time.perf_counter()

    try:
        environment = os.environ.copy()

        benchmark_root = str(BENCHMARK_ROOT.resolve())
        existing_pythonpath = environment.get("PYTHONPATH", "")

        if existing_pythonpath:
            environment["PYTHONPATH"] = (
                benchmark_root
                + os.pathsep
                + existing_pythonpath
            )
        else:
            environment["PYTHONPATH"] = benchmark_root

        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )

        elapsed = time.perf_counter() - start

        output = (
            result.stdout
            + "\n"
            + result.stderr
        )

        return result.returncode, output, elapsed

    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - start

        output = (
            (exc.stdout or "")
            + "\n"
            + (exc.stderr or "")
            + "\nTIMEOUT"
        )

        return -1, output, elapsed


def discover_benchmarks() -> list[Path]:
    if not BENCHMARK_ROOT.exists():
        raise FileNotFoundError(
            f"Benchmark directory does not exist: {BENCHMARK_ROOT}"
        )

    benchmarks = []

    for path in sorted(BENCHMARK_ROOT.iterdir()):
        if not path.is_dir():
            continue

        tests_dir = path / "tests"

        if not tests_dir.is_dir():
            continue

        test_files = sorted(tests_dir.glob("test_*.py"))

        if test_files:
            benchmarks.append(path)

    return benchmarks


def find_test_file(benchmark: Path) -> Path:
    test_files = sorted(
        (benchmark / "tests").glob("test_*.py")
    )

    if not test_files:
        raise FileNotFoundError(
            f"No pytest file found in {benchmark / 'tests'}"
        )

    return test_files[0]


def count_failures(output: str) -> int:
    import re

    for line in reversed(output.splitlines()):
        match = re.search(r"(?<!\d)(\d+)\s+failed\b", line.lower())

        if match:
            return int(match.group(1))

    return 0


def run_baseline(
    benchmark: Path,
    test_file: Path,
) -> tuple[bool, int, str, float]:
    relative_test = test_file.relative_to(benchmark)

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        str(relative_test),
    ]

    return_code, output, elapsed = run_command(
        command,
        benchmark,
    )

    failures = count_failures(output)

    return (
        return_code == 0,
        failures,
        output,
        elapsed,
    )


def build_task(benchmark: Path) -> str:
    return (
        f"Fix the failing tests in the {benchmark.name} benchmark. "
        "Identify the underlying source-code bug, generate a safe "
        "repair, and validate it with targeted and regression tests."
    )


def run_agent(
    benchmark: Path,
    test_file: Path,
) -> tuple[int, str, float]:
    relative_test = test_file.relative_to(benchmark)

    command = [
        sys.executable,
        "-m",
        "app.main",
        "--repository",
        str(benchmark),
        "--tests",
        str(relative_test),
        "--task",
        build_task(benchmark),
    ]

    return run_command(
        command,
        PROJECT_ROOT,
    )


def parse_final_status(output: str) -> str:
    for line in output.splitlines():
        if "Final Status:" in line:
            return line.split("Final Status:", 1)[1].strip()

    if "repair_accepted" in output:
        return "repair_accepted"

    return "unknown"


def parse_count(output: str, label: str) -> int:
    label_text = label.rstrip(":").strip().lower()

    for line in output.splitlines():
        line_text = line.strip()

        if line_text.lower().startswith(label_text + ":"):
            value = line_text.split(":", 1)[1].strip()

            try:
                return int(value)
            except ValueError:
                return 0

    return 0

def parse_pipeline_counts(
    output: str,
) -> tuple[str, int, int, int, int, int, int, int, int, int]:
    status = parse_final_status(output)

    detected = parse_count(output, "Detected Failures:")
    localized = parse_count(output, "Localized Failures:")
    expected = parse_count(output, "Expected Behaviors:")
    contexts = parse_count(output, "Repair Contexts:")
    applied = parse_count(output, "Applied Repairs:")
    decisions = parse_count(output, "Decisions:")

    repair_attempts = parse_count(
        output,
        "Repair Attempts:"
    )

    first_attempt_successes = parse_count(
        output,
        "First-Attempt Successes:"
    )

    retry_assisted_successes = parse_count(
        output,
        "Retry-Assisted Successes:"
    )

    return (
        status,
        detected,
        localized,
        expected,
        contexts,
        applied,
        decisions,
        repair_attempts,
        first_attempt_successes,
        retry_assisted_successes,
    )


def restore_benchmark(benchmark: Path) -> None:
    relative_path = benchmark.relative_to(PROJECT_ROOT)

    command = [
        "git",
        "restore",
        "--",
        str(relative_path),
    ]

    return_code, output, _ = run_command(
        command,
        PROJECT_ROOT,
    )

    if return_code != 0:
        print(
            "WARNING: Could not restore benchmark:",
            benchmark.name,
        )
        print(output)


def evaluate_benchmark(benchmark: Path) -> BenchmarkResult:
    test_file = find_test_file(benchmark)

    print("\n" + "=" * 70)
    print(f"Benchmark: {benchmark.name}")
    print("=" * 70)

    baseline_passed, baseline_failures, baseline_output, baseline_time = (
        run_baseline(benchmark, test_file)
    )

    print(
        "[1B] Baseline:",
        "PASS" if baseline_passed else f"FAIL ({baseline_failures} failure(s))",
    )

    if baseline_passed:
        return BenchmarkResult(
            name=benchmark.name,
            path=str(benchmark.relative_to(PROJECT_ROOT)),
            test_file=str(test_file.relative_to(benchmark)),
            baseline_passed=True,
            baseline_failures=0,
            final_status="skipped_baseline_passed",
            detected_failures=0,
            localized_failures=0,
            expected_behaviors=0,
            repair_contexts=0,
            applied_repairs=0,
            decisions=0,
            repair_attempts=0,
            first_attempt_successes=0,
            retry_assisted_successes=0,
            repair_accepted=False,
            regression_free=False,
            elapsed_seconds=baseline_time,
            error="Benchmark does not reproduce a failing test.",
        )

    print("[1C] Running autonomous repair agent...")

    return_code, agent_output, agent_time = run_agent(
        benchmark,
        test_file,
    )

    (
        status,
        detected,
        localized,
        expected,
        contexts,
        applied,
        decisions,
        repair_attempts,
        first_attempt_successes,
        retry_assisted_successes,
    ) = parse_pipeline_counts(agent_output)

    repair_accepted = status == "repair_accepted"

    regression_free = (
        repair_accepted
        and (
            "NO NEW REGRESSIONS" in agent_output
            or "Regression tests passed" in agent_output
            or (
                "regression" in agent_output.lower()
                and "passed" in agent_output.lower()
            )
        )
    )

    print("[1D] Final status:", status)
    print("[1D] Detected failures:", detected)
    print("[1D] Localized failures:", localized)
    print("[1D] Expected behaviors:", expected)
    print("[1D] Repair contexts:", contexts)
    print("[1D] Applied repairs:", applied)
    print("[1D] Decisions:", decisions)
    print("[1D] Repair attempts:", repair_attempts)
    print("[1D] First-attempt successes:", first_attempt_successes)
    print("[1D] Retry-assisted successes:", retry_assisted_successes)
    print(
        "[1D] Repair accepted:",
        "YES" if repair_accepted else "NO",
    )
    print(
        "[1D] Regression-free:",
        "YES" if regression_free else "NO",
    )

    restore_benchmark(benchmark)

    return BenchmarkResult(
        name=benchmark.name,
        path=str(benchmark.relative_to(PROJECT_ROOT)),
        test_file=str(test_file.relative_to(benchmark)),
        baseline_passed=baseline_passed,
        baseline_failures=baseline_failures,
        final_status=status,
        detected_failures=detected,
        localized_failures=localized,
        expected_behaviors=expected,
        repair_contexts=contexts,
        applied_repairs=applied,
        decisions=decisions,
        repair_attempts=repair_attempts,
        first_attempt_successes=first_attempt_successes,
        retry_assisted_successes=retry_assisted_successes,
        repair_accepted=repair_accepted,
        regression_free=regression_free,
        elapsed_seconds=baseline_time + agent_time,
        error=(
            None
            if return_code == 0 or repair_accepted
            else "Repair pipeline exited with a non-zero status."
        ),
    )


def calculate_metrics(
    results: list[BenchmarkResult],
) -> dict:
    total = len(results)

    reproducible = sum(
        not result.baseline_passed
        for result in results
    )

    successful = sum(
        result.repair_accepted
        for result in results
    )

    regression_free = sum(
        result.regression_free
        for result in results
    )

    total_repair_attempts = sum(
        result.repair_attempts
        for result in results
    )

    first_attempt_successes = sum(
        result.first_attempt_successes
        for result in results
    )

    retry_assisted_successes = sum(
        result.retry_assisted_successes
        for result in results
    )

    average_repair_attempts = (
        total_repair_attempts / reproducible
        if reproducible
        else 0.0
    )

    maximum_repair_attempts = max(
        (
            result.repair_attempts
            for result in results
        ),
        default=0,
    )

    total_evaluation_time = sum(
        result.elapsed_seconds
        for result in results
    )

    return {
        "total_benchmarks": total,
        "reproducible_failures": reproducible,
        "successful_repairs": successful,
        "regression_free_repairs": regression_free,

        "repair_success_rate": (
            successful / reproducible
            if reproducible
            else 0.0
        ),

        "regression_free_rate": (
            regression_free / successful
            if successful
            else 0.0
        ),

        "total_repair_attempts": total_repair_attempts,

        "first_attempt_successes": first_attempt_successes,

        "retry_assisted_successes": retry_assisted_successes,

        "first_attempt_success_rate": (
            first_attempt_successes / reproducible
            if reproducible
            else 0.0
        ),

        "retry_assisted_rate": (
            retry_assisted_successes / reproducible
            if reproducible
            else 0.0
        ),

        "average_repair_attempts": round(
            average_repair_attempts,
            2,
        ),

        "maximum_repair_attempts": maximum_repair_attempts,

        "total_evaluation_time_seconds": round(
            total_evaluation_time,
            2,
        ),

        "average_evaluation_time_seconds": round(
            total_evaluation_time / total
            if total
            else 0.0,
            2,
        ),
    }



def write_json(
    results: list[BenchmarkResult],
    metrics: dict,
) -> None:
    payload = {
        "project": "Autonomous Code Repair Agent",
        "benchmarks": [
            asdict(result)
            for result in results
        ],
        "metrics": metrics,
    }

    RESULTS_FILE.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def write_markdown(
    results: list[BenchmarkResult],
    metrics: dict,
) -> None:
    lines = [
        "# Autonomous Code Repair Agent — Evaluation Report",
        "",
        "## Summary",
        "",
        f"- Total benchmarks: **{metrics['total_benchmarks']}**",
        (
            "- Reproducible failing benchmarks: "
            f"**{metrics['reproducible_failures']}**"
        ),
        f"- Successful repairs: **{metrics['successful_repairs']}**",
        (
            "- Regression-free repairs: "
            f"**{metrics['regression_free_repairs']}**"
        ),
        (
            "- Repair success rate: "
            f"**{metrics['repair_success_rate'] * 100:.1f}%**"
        ),
        (
            "- Regression-free rate: "
            f"**{metrics['regression_free_rate'] * 100:.1f}%**"
        ),
        "",
        "## Repair Attempt Analysis",
        "",
        (
            "- Total repair attempts: "
            f"**{metrics['total_repair_attempts']}**"
        ),
        (
            "- First-attempt successes: "
            f"**{metrics['first_attempt_successes']}**"
        ),
        (
            "- Retry-assisted successes: "
            f"**{metrics['retry_assisted_successes']}**"
        ),
        (
            "- First-attempt success rate: "
            f"**{metrics['first_attempt_success_rate'] * 100:.1f}%**"
        ),
        (
            "- Retry-assisted rate: "
            f"**{metrics['retry_assisted_rate'] * 100:.1f}%**"
        ),
        (
            "- Average repair attempts: "
            f"**{metrics['average_repair_attempts']:.2f}**"
        ),
        (
            "- Maximum repair attempts: "
            f"**{metrics['maximum_repair_attempts']}**"
        ),
        "",
        "## Evaluation Time",
        "",
        (
            "- Total evaluation time: "
            f"**{metrics['total_evaluation_time_seconds']}s**"
        ),
        (
            "- Average evaluation time: "
            f"**{metrics['average_evaluation_time_seconds']}s**"
        ),
        "",
        "## Benchmark Results",
        "",
        "| Benchmark | Baseline | Repair | Regression | Attempts | Time |",
        "|---|---|---|---|---:|---:|",
    ]

    for result in results:
        baseline = (
            "PASS"
            if result.baseline_passed
            else "FAIL"
        )

        repair = (
            "PASS"
            if result.repair_accepted
            else "FAIL"
        )

        regression = (
            "PASS"
            if result.regression_free
            else "FAIL"
        )

        lines.append(
            f"| {result.name} | {baseline} | "
            f"{repair} | {regression} | "
            f"{result.repair_attempts} | "
            f"{result.elapsed_seconds:.1f}s |"
        )

    lines.extend(
        [
            "",
            "## Methodology",
            "",
            "Each benchmark contains a seeded software defect.",
            "The evaluator first verifies that the defect reproduces "
            "through the benchmark test suite.",
            "",
            "The autonomous repair pipeline is then executed against "
            "the benchmark.",
            "",
            "A repair is considered successful when the pipeline accepts "
            "the generated repair after validation.",
            "",
            "A regression-free repair is one that is accepted without "
            "introducing new regression failures.",
            "",
            "Repair attempts measure the number of generated repair "
            "attempts required for a benchmark repair.",
            "",
            "First-attempt successes are repairs accepted after the "
            "initial generated repair.",
            "",
            "Retry-assisted successes are repairs that required at "
            "least one additional repair attempt.",
            "",
        ]
    )

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )



def main() -> None:
    print("=" * 70)
    print("AUTONOMOUS CODE REPAIR — BENCHMARK EVALUATION")
    print("=" * 70)

    benchmarks = discover_benchmarks()

    print(
        f"\n[1A] Discovered benchmarks: {len(benchmarks)}"
    )

    for benchmark in benchmarks:
        print(f"      - {benchmark.name}")

    results = []

    for benchmark in benchmarks:
        try:
            result = evaluate_benchmark(benchmark)
        except Exception as exc:
            print(
                f"[ERROR] {benchmark.name}: {exc}"
            )

            result = BenchmarkResult(
                name=benchmark.name,
                path=str(benchmark.relative_to(PROJECT_ROOT)),
                test_file="",
                baseline_passed=False,
                baseline_failures=0,
                final_status="evaluation_error",
                detected_failures=0,
                localized_failures=0,
                expected_behaviors=0,
                repair_contexts=0,
                applied_repairs=0,
                decisions=0,
                repair_attempts=0,
                first_attempt_successes=0,
                retry_assisted_successes=0,
                repair_accepted=False,
                regression_free=False,
                elapsed_seconds=0.0,
                error=str(exc),
            )

        results.append(result)

    metrics = calculate_metrics(results)

    write_json(results, metrics)
    write_markdown(results, metrics)

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    print(
        f"Total benchmarks:          "
        f"{metrics['total_benchmarks']}"
    )

    print(
        f"Reproducible failures:     "
        f"{metrics['reproducible_failures']}"
    )

    print(
        f"Successful repairs:        "
        f"{metrics['successful_repairs']}"
    )

    print(
        f"Regression-free repairs:   "
        f"{metrics['regression_free_repairs']}"
    )

    print(
        f"Repair success rate:       "
        f"{metrics['repair_success_rate'] * 100:.1f}%"
    )

    print(
        f"Regression-free rate:      "
        f"{metrics['regression_free_rate'] * 100:.1f}%"
    )

    print(
        f"Total evaluation time:     "
        f"{metrics['total_evaluation_time_seconds']}s"
    )

    print(
        f"Average evaluation time:   "
        f"{metrics['average_evaluation_time_seconds']}s"
    )

    print("\nGenerated:")
    print(f"  {RESULTS_FILE}")
    print(f"  {REPORT_FILE}")


if __name__ == "__main__":
    main()
