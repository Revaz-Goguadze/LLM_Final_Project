import ast
import os
from typing import List, Dict, Any

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
        pass

    def chunk_file(self, file_path: str) -> List[CodeChunk]:
        """Chunks a file into functions and classes using AST."""
        if not file_path.endswith('.py'):
            # For now, only support Python via built-in AST
            # TODO: Add tree-sitter support for JS/TS
            return self._simple_chunk(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            chunks = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    # Extract the lines for this node
                    lines = source.splitlines()
                    start = node.lineno
                    end = getattr(node, 'end_lineno', start + 1) # end_lineno added in 3.8
                    
                    chunk_content = "\n".join(lines[start-1:end])
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
            return [CodeChunk(
                content=source,
                file_path=file_path,
                start_line=1,
                end_line=len(source.splitlines()),
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
