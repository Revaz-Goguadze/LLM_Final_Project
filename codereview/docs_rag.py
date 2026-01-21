import os
from .chroma_client import get_chroma_client
from .embeddings import get_embedding_function

DOCS_COLLECTION = "best_practices_docs"

class DocsIndexer:
    """Indexes best practices and documentation for the Documentation RAG."""
    
    def __init__(self):
        self.client = get_chroma_client()
        self.emb_fn = get_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name=DOCS_COLLECTION,
            embedding_function=self.emb_fn
        )

    def index_docs_directory(self, directory: str = "docs"):
        """Indexes all markdown files in the docs directory."""
        if not os.path.exists(directory):
            print(f"Docs directory {directory} not found.")
            return
            
        for filename in os.listdir(directory):
            if filename.endswith('.md'):
                filepath = os.path.join(directory, filename)
                self.index_doc_file(filepath)

    def index_doc_file(self, filepath: str):
        """Indexes a single documentation file by sections."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by headers (## sections)
        sections = self._split_by_headers(content)
        
        ids = []
        documents = []
        metadatas = []
        
        for i, section in enumerate(sections):
            section_id = f"{filepath}:section_{i}"
            ids.append(section_id)
            documents.append(section['content'])
            metadatas.append({
                "file": filepath,
                "title": section['title'],
                "type": "best_practice"
            })
        
        if ids:
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            print(f"Indexed {len(sections)} sections from {filepath}")

    def _split_by_headers(self, content: str) -> list:
        """Splits markdown content by ## headers."""
        sections = []
        current_title = "Introduction"
        current_content = []
        
        for line in content.split('\n'):
            if line.startswith('## '):
                if current_content:
                    sections.append({
                        'title': current_title,
                        'content': '\n'.join(current_content)
                    })
                current_title = line[3:].strip()
                current_content = [line]
            else:
                current_content.append(line)
        
        if current_content:
            sections.append({
                'title': current_title,
                'content': '\n'.join(current_content)
            })
        
        return sections


class DocsRetriever:
    """Retrieves relevant best practices based on the code being analyzed."""
    
    def __init__(self):
        self.client = get_chroma_client()
        self.emb_fn = get_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name=DOCS_COLLECTION,
            embedding_function=self.emb_fn
        )

    def search(self, query: str, n_results: int = 5) -> list:
        """Searches for relevant documentation sections."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        formatted = []
        if not results.get("ids") or not results["ids"] or not results["ids"][0]:
            return formatted
        for i in range(len(results['ids'][0])):
            formatted.append({
                "id": results['ids'][0][i],
                "content": results['documents'][0][i],
                "metadata": results['metadatas'][0][i],
                "distance": results['distances'][0][i]
            })
        return formatted


if __name__ == "__main__":
    # Index all docs
    indexer = DocsIndexer()
    indexer.index_docs_directory("docs")
    
    # Test retrieval
    retriever = DocsRetriever()
    results = retriever.search("SQL injection prevention")
    for r in results:
        print(f"Found: {r['metadata']['title']}")
        print(f"Content: {r['content'][:100]}...")
