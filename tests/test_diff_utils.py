from codereview.diff_utils import parse_unified_diff_files


def test_parse_unified_diff_files_multiple():
    diff = (
        "diff --git a/foo.py b/foo.py\n"
        "index 111..222 100644\n"
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
        "diff --git a/bar.py b/bar.py\n"
        "index 333..444 100644\n"
        "--- a/bar.py\n"
        "+++ b/bar.py\n"
    )
    assert parse_unified_diff_files(diff) == ["foo.py", "bar.py"]
