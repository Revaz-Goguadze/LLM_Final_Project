import os


def read_file(filename):
    # BUG: Path traversal vulnerability
    filepath = f"/var/data/{filename}"
    with open(filepath, "r") as f:
        return f.read()


def download_file(user_path):
    # BUG: No path validation - allows ../../../etc/passwd
    base_dir = "/uploads"
    return open(os.path.join(base_dir, user_path), "rb").read()
