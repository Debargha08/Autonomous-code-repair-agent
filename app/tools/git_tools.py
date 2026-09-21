from pathlib import Path
import os
import subprocess


def _run_git(repository_path, *args):
    """
    Run a Git command from the actual repository root.

    This ensures repository-root-relative paths passed to Git
    are interpreted consistently even when repository_path is
    a nested directory.
    """
    repository_path = Path(repository_path).resolve()

    root_result = subprocess.run(
        [
            "git",
            "-C",
            str(repository_path),
            "rev-parse",
            "--show-toplevel",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    repository_root = root_result.stdout.strip()

    return subprocess.run(
        ["git", *args],
        cwd=repository_root,
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

    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        return False


def get_repository_root(repository_path):
    """
    Return the actual Git repository root containing
    repository_path.
    """
    result = _run_git(
        repository_path,
        "rev-parse",
        "--show-toplevel",
    )

    return os.path.abspath(
        result.stdout.strip()
    )


def get_relative_target_path(
    repository_path,
    target_path,
):
    """
    Convert a target path into a path relative to the
    actual Git repository root.
    """
    repository_root = get_repository_root(
        repository_path
    )

    full_target = os.path.abspath(
        os.path.join(
            repository_path,
            target_path,
        )
    )

    try:
        return os.path.relpath(
            full_target,
            repository_root,
        )

    except ValueError as error:
        raise RuntimeError(
            "Target path is not compatible with "
            "the Git repository root."
        ) from error


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


def create_repair_checkpoint(
    repository_path,
    target_files=None,
    message="repair checkpoint",
):
    """
    Create a safe repair checkpoint.

    No files are staged or committed.

    The checkpoint records:
        - repository root
        - current HEAD
        - target paths
        - their current tracked/untracked state

    The working tree must be clean for the target paths.
    Unrelated changes elsewhere in the repository are allowed.
    """
    repository_root = get_repository_root(
        repository_path
    )

    target_files = target_files or []

    relative_targets = []

    for target_file in target_files:
        relative_targets.append(
            get_relative_target_path(
                repository_path,
                target_file,
            )
        )

    status = get_working_tree_status(
        repository_path
    )

    if status:
        changed_paths = []

        for line in status.splitlines():

            if len(line) >= 4:
                changed_paths.append(
                    line[3:]
                )

        for changed_path in changed_paths:

            for target in relative_targets:

                if (
                    changed_path == target
                    or changed_path.startswith(
                        target + os.sep
                    )
                ):
                    raise RuntimeError(
                        "Cannot create repair checkpoint "
                        "because a target file already has "
                        "uncommitted changes: "
                        f"{changed_path}"
                    )

    return {
        "repository_root": repository_root,
        "commit": get_current_commit(
            repository_path
        ),
        "target_files": relative_targets,
        "message": message,
    }


def rollback_to_checkpoint(
    repository_path,
    checkpoint,
):
    """
    Restore ONLY the files belonging to the repair
    checkpoint.

    The repository HEAD is never reset.

    Tracked target files are restored to the checkpoint
    commit.

    Files that did not exist at the checkpoint are removed
    if they were created by the repair.
    """
    repository_root = checkpoint[
        "repository_root"
    ]

    current_root = get_repository_root(
        repository_path
    )

    if (
        os.path.abspath(repository_root)
        != os.path.abspath(current_root)
    ):
        raise RuntimeError(
            "Checkpoint repository root does not match "
            "the current repository."
        )

    commit = checkpoint["commit"]

    for target in checkpoint["target_files"]:

        target_full_path = os.path.join(
            repository_root,
            target,
        )

        result = subprocess.run(
            [
                "git",
                "cat-file",
                "-e",
                f"{commit}:{target}",
            ],
            cwd=repository_root,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:

            subprocess.run(
                [
                    "git",
                    "restore",
                    "--source",
                    commit,
                    "--",
                    target,
                ],
                cwd=repository_root,
                check=True,
            )

        else:

            if os.path.isfile(
                target_full_path
            ):
                os.remove(
                    target_full_path
                )

            elif os.path.isdir(
                target_full_path
            ):
                raise RuntimeError(
                    "Refusing to recursively delete "
                    f"directory created during repair: "
                    f"{target}"
                )


def rollback_to_commit(
    repository_path,
    commit_sha,
    target_files,
):
    """
    Backward-compatible path-scoped rollback.

    IMPORTANT:
    This never performs `git reset --hard` and never
    performs repository-wide `git clean`.
    """
    checkpoint = {
        "repository_root": get_repository_root(
            repository_path
        ),
        "commit": commit_sha,
        "target_files": [
            get_relative_target_path(
                repository_path,
                target_file,
            )
            for target_file in target_files
        ],
    }

    rollback_to_checkpoint(
        repository_path,
        checkpoint,
    )


def get_changed_files(repository_path, target_files=None):
    """
    Return files changed relative to HEAD.

    target_files are paths relative to the Git repository root
    or absolute paths.
    """
    args = ["diff", "--name-only"]

    if target_files:
        repository_root = Path(
            get_repository_root(repository_path)
        ).resolve()

        normalized_targets = []

        for target_file in target_files:
            target_path = Path(target_file)

            if target_path.is_absolute():
                target_path = target_path.resolve()
            else:
                target_path = (
                    repository_root / target_path
                ).resolve()

            try:
                relative_path = target_path.relative_to(
                    repository_root
                )
            except ValueError as exc:
                raise ValueError(
                    f"Target file is outside the repository: "
                    f"{target_file}"
                ) from exc

            normalized_targets.append(str(relative_path))

        args.extend(["--", *normalized_targets])

    result = _run_git(repository_path, *args)

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def get_diff(repository_path, target_files=None):
    """
    Return the current working-tree diff relative to HEAD.

    target_files are paths relative to the Git repository root
    or absolute paths.
    """
    args = [
        "diff",
        "--no-ext-diff",
        "--unified=3",
    ]

    if target_files:
        repository_root = Path(
            get_repository_root(repository_path)
        ).resolve()

        normalized_targets = []

        for target_file in target_files:
            target_path = Path(target_file)

            if target_path.is_absolute():
                target_path = target_path.resolve()
            else:
                target_path = (
                    repository_root / target_path
                ).resolve()

            try:
                relative_path = target_path.relative_to(
                    repository_root
                )
            except ValueError as exc:
                raise ValueError(
                    f"Target file is outside the repository: "
                    f"{target_file}"
                ) from exc

            normalized_targets.append(str(relative_path))

        args.extend(["--", *normalized_targets])

    result = _run_git(repository_path, *args)

    return result.stdout
