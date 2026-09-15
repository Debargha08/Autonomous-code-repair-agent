import os


def list_files(repository_path):

    files = []

    for root, directories, filenames in os.walk(repository_path):

        directories[:] = [
            directory
            for directory in directories
            if directory not in {".git", "__pycache__", ".venv", "venv"}
        ]

        for filename in filenames:
            files.append(os.path.relpath(
                os.path.join(root, filename),
                repository_path
            ))

    return files


def read_file(repository_path, file_path):

    full_path = os.path.join(repository_path, file_path)

    if not os.path.isfile(full_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(full_path, "r", encoding="utf-8") as file:
        return file.read()