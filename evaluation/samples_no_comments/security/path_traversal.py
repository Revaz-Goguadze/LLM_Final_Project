import os

def read_user_file(filename):
    base_path = "/var/app/uploads"
    full_path = os.path.join(base_path, filename)
    with open(full_path, "r") as f:
        return f.read()


def delete_user_file(filename):
    base_path = "/var/app/uploads"
    full_path = os.path.join(base_path, filename)
    os.remove(full_path)
