import ast
import os
from typing import List, Dict, Any

try:
    from tree_sitter_languages import get_parser
except Exception:
    get_parser = None

class CodeChunk:
    def __init__(self, content: str, file_path: str, start_line: int, end_line: int, name: str, type: str):
        self.content = content
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.name = name
        self.type = type # 'function', 'class', 'module'

class ASTChunker:
    def __init__(self):
        self._ts_parsers = {}
        self._max_line_digits = 6

    def _get_ts_parser(self, language: str):
        if not get_parser:
            return None
        if language not in self._ts_parsers:
            self._ts_parsers[language] = get_parser(language)
        return self._ts_parsers[language]

    def _with_line_numbers(self, lines: List[str], start_line: int, end_line: int) -> str:
        width = max(self._max_line_digits, len(str(end_line)))
        numbered = [
            f"{i:>{width}}: {lines[i - 1]}"
            for i in range(start_line, end_line + 1)
            if 0 < i <= len(lines)
        ]
        return "\n".join(numbered)

    def _chunk_with_tree_sitter(self, file_path: str, language: str) -> List[CodeChunk]:
        parser = self._get_ts_parser(language)
        if not parser:
            return self._simple_chunk(file_path)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception:
            return []

        tree = parser.parse(bytes(source, "utf-8"))
        lines = source.splitlines()
        chunks: List[CodeChunk] = []
        target_types = {
            "function_declaration",
            "class_declaration",
            "method_definition",
            "arrow_function",
        }

        cursor = tree.walk()
        stack = [cursor.node]
        while stack:
            node = stack.pop()
            if node.type in target_types:
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                chunk_content = self._with_line_numbers(lines, start_line, end_line)
                name = node.type
                if node.child_by_field_name("name"):
                    name_node = node.child_by_field_name("name")
                    name = source[name_node.start_byte:name_node.end_byte]
                chunks.append(
                    CodeChunk(
                        content=chunk_content,
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        name=name,
                        type="function" if "function" in node.type else "class",
                    )
                )
            stack.extend(reversed(node.children))

        if not chunks:
            return self._simple_chunk(file_path)
        return chunks

    def chunk_file(self, file_path: str) -> List[CodeChunk]:
        """Chunks a file into functions and classes using AST."""
        if not file_path.endswith('.py'):
            ext = os.path.splitext(file_path)[1].lower()
            if ext in {".js", ".jsx"}:
                return self._chunk_with_tree_sitter(file_path, "javascript")
            if ext in {".ts", ".tsx"}:
                return self._chunk_with_tree_sitter(file_path, "typescript")
            return self._simple_chunk(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            lines = source.splitlines()
            chunks = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    # Extract the lines for this node
                    start = node.lineno
                    if getattr(node, "decorator_list", None):
                        decorator_lines = [
                            getattr(dec, "lineno", start)
                            for dec in node.decorator_list
                        ]
                        start = min([start] + decorator_lines)
                    end = getattr(node, 'end_lineno', start) # end_lineno added in 3.8
                    
                    chunk_content = self._with_line_numbers(lines, start, end)
                    node_type = 'class' if isinstance(node, ast.ClassDef) else 'function'
                    
                    chunks.append(CodeChunk(
                        content=chunk_content,
                        file_path=file_path,
                        start_line=start,
                        end_line=end,
                        name=node.name,
                        type=node_type
                    ))
            
            # If no chunks found, treat entry file as module
            if not chunks:
                chunks.append(CodeChunk(
                    content=source,
                    file_path=file_path,
                    start_line=1,
                    end_line=len(source.splitlines()),
                    name=os.path.basename(file_path),
                    type='module'
                ))
                
            return chunks
        except Exception as e:
            print(f"Error chunking {file_path}: {e}")
            return self._simple_chunk(file_path)

    def _simple_chunk(self, file_path: str) -> List[CodeChunk]:
        """Fallback simple chunking by line count or just whole file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            lines = source.splitlines()
            end_line = len(lines)
            return [CodeChunk(
                content=self._with_line_numbers(lines, 1, end_line),
                file_path=file_path,
                start_line=1,
                end_line=end_line,
                name=os.path.basename(file_path),
                type='module'
            )]
        except Exception:
            return []

if __name__ == "__main__":
    chunker = ASTChunker()
    file = __file__ # test on itself
    chunks = chunker.chunk_file(file)
    for c in chunks:
        print(f"--- {c.type}: {c.name} ({c.start_line}-{c.end_line}) ---")
        # print(c.content[:50] + "...")
