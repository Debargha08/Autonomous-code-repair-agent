import os


def scan_repository(state):

    repository_path = state["repository_path"]

    relevant_files = []

    ignored_directories = {
        ".git",
        ".pytest_cache",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "node_modules",
    }

    allowed_extensions = {
        ".py",
        ".js",
        ".ts",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
    }

    for root, directories, files in os.walk(repository_path):

        # Prevent scanning unnecessary directories
        directories[:] = [
            directory
            for directory in directories
            if directory not in ignored_directories
        ]

        for file in files:

            extension = os.path.splitext(file)[1]

            if extension not in allowed_extensions:
                continue

            full_path = os.path.join(root, file)

            relative_path = os.path.relpath(
                full_path,
                repository_path
            )

            relevant_files.append(relative_path)

    print("\n================ SCANNER ================\n")

    for file_path in relevant_files:
        print(file_path)

    print("\n==========================================\n")

    return {
        "relevant_files": relevant_files,
        "status": "repository_scanned"
    }