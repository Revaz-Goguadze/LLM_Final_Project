import pytest

from codereview.chunker import ASTChunker


def test_chunker_js_functions(tmp_path):
    pytest.importorskip("tree_sitter_languages")
    js_file = tmp_path / "sample.js"
    js_file.write_text(
        "function add(a, b) {\n  return a + b;\n}\n\nclass Foo {\n  bar() {\n    return 1;\n  }\n}\n",
        encoding="utf-8",
    )

    chunker = ASTChunker()
    chunks = chunker.chunk_file(str(js_file))
    assert chunks
    types = {c.type for c in chunks}
    assert "function" in types or "class" in types
