import subprocess


def _run_git(repository_path, *args):
    """
    Run a Git command inside the repository.
    """
    return subprocess.run(
        ["git", *args],
        cwd=repository_path,
        capture_output=True,
        text=True,
        check=True,
    )


def is_git_repository(repository_path):
    """
    Check whether the supplied path is inside a Git repository.
    """
    try:
        result = _run_git(
            repository_path,
            "rev-parse",
            "--is-inside-work-tree",
        )

        return result.stdout.strip() == "true"

    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_current_commit(repository_path):
    """
    Return the current HEAD commit SHA.
    """
    result = _run_git(
        repository_path,
        "rev-parse",
        "HEAD",
    )

    return result.stdout.strip()


def get_working_tree_status(repository_path):
    """
    Return the current Git working-tree status.
    """
    result = _run_git(
        repository_path,
        "status",
        "--porcelain",
    )

    return result.stdout.strip()


def create_repair_checkpoint(repository_path, message="repair checkpoint"):
    """
    Create a Git checkpoint from the repository's current state.

    IMPORTANT:
    This function does NOT stage or commit files automatically.

    The repair system should only create a checkpoint when the
    repository is already clean. This prevents unrelated user
    changes from being committed accidentally.
    """
    status = get_working_tree_status(repository_path)

    if status:
        raise RuntimeError(
            "Cannot create repair checkpoint because the "
            "repository has uncommitted changes. "
            "Commit or otherwise isolate existing changes first."
        )

    return get_current_commit(repository_path)


def rollback_to_commit(repository_path, commit_sha):
    """
    Restore the repository to a specific commit.

    Tracked files are restored to the checkpoint state.
    Untracked files created by the failed repair are removed.
    """
    _run_git(
        repository_path,
        "reset",
        "--hard",
        commit_sha,
    )

    _run_git(
        repository_path,
        "clean",
        "-fd",
    )


def get_changed_files(repository_path):
    """
    Return files changed relative to HEAD.
    """
    result = _run_git(
        repository_path,
        "diff",
        "--name-only",
    )

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]
