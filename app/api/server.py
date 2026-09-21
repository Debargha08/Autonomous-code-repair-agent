from pathlib import Path
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agent.repair_agent import run_repair_pipeline
from app.tools.git_tools import (
    get_changed_files,
    get_diff,
)


app = FastAPI(
    title="Autonomous Code Repair Agent",
    description=(
        "API for autonomous software repair using failure analysis, "
        "LLM-generated repairs, targeted testing, regression testing, "
        "and Git-safe rollback."
    ),
    version="1.0.0",
)


class RepairRequest(BaseModel):
    repository_path: str = Field(
        description="Path to the repository containing the failing code."
    )
    task: str = Field(
        default="Find and fix the failing source code.",
        description="Natural-language task describing the repair objective."
    )
    tests: str | None = Field(
        default=None,
        description="Optional pytest path or test selection to run."
    )


class RepairResponse(BaseModel):
    job_id: str = Field(
        description="Unique identifier of the repair job."
    )
    status: str = Field(
        description="Initial job status."
    )


class JobStatusResponse(BaseModel):
    job_id: str = Field(
        description="Unique identifier of the repair job."
    )
    status: str = Field(
        description="Current job status."
    )
    progress: str = Field(
        description="Current execution stage of the repair job."
    )
    created_at: str = Field(
        description="UTC timestamp when the job was created."
    )
    started_at: str | None = Field(
        default=None,
        description="UTC timestamp when execution started."
    )
    completed_at: str | None = Field(
        default=None,
        description="UTC timestamp when execution completed."
    )
    result: dict | None = Field(
        default=None,
        description="Repair metrics and Git diff information when available."
    )
    error: str | None = Field(
        default=None,
        description="Error message when job execution fails."
    )


jobs: dict[str, dict] = {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress: str | None = None,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    job = jobs[job_id]

    if status is not None:
        job["status"] = status

    if progress is not None:
        job["progress"] = progress

    if result is not None:
        job["result"] = result

    if error is not None:
        job["error"] = error


def run_tests(
    repository_path: str,
    tests_path: str | None = None,
) -> str:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
    ]

    if tests_path:
        command.append(tests_path)

    result = subprocess.run(
        command,
        cwd=repository_path,
        capture_output=True,
        text=True,
    )

    return result.stdout + "\n" + result.stderr


def execute_repair(
    job_id: str,
    repository_path: str,
    task: str,
    tests: str | None,
) -> None:
    try:
        update_job(
            job_id,
            status="running",
            progress="running_initial_tests",
        )

        jobs[job_id]["started_at"] = now()

        test_output = run_tests(
            repository_path,
            tests,
        )

        update_job(
            job_id,
            progress="running_repair_pipeline",
        )

        result = run_repair_pipeline(
            repository_path=repository_path,
            test_output=test_output,
            task=task,
        )

        pipeline_status = result.get(
            "status",
            "unknown",
        )

        if pipeline_status in {
            "repair_accepted",
            "no_failures",
        }:
            final_status = "completed"
            progress = "repair_completed"
        else:
            final_status = "completed"
            progress = "repair_finished"

        changed_files = []
        diff = ""

        if pipeline_status == "repair_accepted":
            try:
                repair_targets = [
                    repair["source_file"]
                    for repair in result.get(
                        "applied_repairs",
                        []
                    )
                    if repair.get("source_file")
                ]

                changed_files = get_changed_files(
                    repository_path,
                    repair_targets,
                )

                diff = get_diff(
                    repository_path,
                    repair_targets,
                )
            except Exception as diff_error:
                update_job(
                    job_id,
                    progress="repair_completed_diff_unavailable",
                    error=(
                        "Repair completed, but Git diff "
                        f"generation failed: {diff_error}"
                    ),
                )

        update_job(
            job_id,
            status=final_status,
            progress=progress,
            result={
                "status": pipeline_status,
                "failures": len(
                    result.get("failures", [])
                ),
                "localized_failures": len(
                    result.get("localized_failures", [])
                ),
                "expected_behaviors": len(
                    result.get("expected_behaviors", [])
                ),
                "repair_contexts": len(
                    result.get("repair_contexts", [])
                ),
                "applied_repairs": len(
                    result.get("applied_repairs", [])
                ),
                "decisions": len(
                    result.get("decisions", [])
                ),
                "changed_files": changed_files,
                "diff": diff,
            },
        )

    except subprocess.TimeoutExpired:
        update_job(
            job_id,
            status="failed",
            progress="initial_tests_timed_out",
            error="Initial test execution timed out.",
        )

    except Exception as exc:
        update_job(
            job_id,
            status="failed",
            progress="execution_failed",
            error=str(exc),
        )

    finally:
        jobs[job_id]["completed_at"] = now()


@app.get(
    "/health",
    summary="Health check",
    description="Check whether the autonomous code repair API is running.",
    tags=["System"],
)
def health():
    return {
        "status": "ok",
        "service": "autonomous-code-repair-agent",
    }


@app.post(
    "/repair",
    response_model=RepairResponse,
    summary="Start a repair job",
    description=(
        "Start an autonomous code repair job. The repair executes "
        "asynchronously and can be monitored using the returned job ID."
    ),
    tags=["Repair"],
)
def repair(request: RepairRequest):
    repository = (
        Path(request.repository_path)
        .expanduser()
        .resolve()
    )

    if not repository.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Repository does not exist: {repository}",
        )

    if not repository.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Repository path is not a directory: {repository}",
        )

    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": "job_created",
        "created_at": now(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }

    worker = threading.Thread(
        target=execute_repair,
        args=(
            job_id,
            str(repository),
            request.task,
            request.tests,
        ),
        daemon=True,
    )

    worker.start()

    return RepairResponse(
        job_id=job_id,
        status="queued",
    )


@app.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get repair job status",
    description=(
        "Retrieve the current status, progress, result metrics, "
        "and Git diff for a repair job."
    ),
    tags=["Jobs"],
)
def get_job(job_id: str):
    job = jobs.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}",
        )

    return job
