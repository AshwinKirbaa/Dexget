import os
import re
import json
from typing import List, Dict

class RAGCore:
    def __init__(self):
        self.db_path = os.path.expanduser("~/.jarvis/rag_docs.json")
        self.documents = []
        self.load_db()
        
    def load_db(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self.documents = json.load(f)
            except Exception:
                self.documents = []
                
    def save_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.documents, f, indent=2)
    
    def ingest_document(self, file_path: str):
        from jarvis.memory.document_intelligence import DocumentExtractor
        text = DocumentExtractor.extract_text(file_path)
        if not text.startswith("Error") and text.strip():
            # Check if already exists, then update
            found = False
            for d in self.documents:
                if d["path"] == file_path:
                    d["content"] = text
                    d["metadata"]["type"] = os.path.splitext(file_path)[1]
                    found = True
                    break
            if not found:
                self.documents.append({
                    "path": file_path,
                    "content": text,
                    "metadata": {"source": file_path, "type": os.path.splitext(file_path)[1]}
                })
            self.save_db()
            
    def query(self, text_query: str, top_k: int = 3, threshold: float = 1.0) -> List[Dict]:
        """
        Use lexical, phrase and semantic matching.
        Require a strong threshold to avoid false positives on generic queries like "what is data?".
        """
        query_words = set(re.findall(r'\w+', text_query.lower()))
        # Filter out common stop words
        stop_words = {"what", "is", "the", "a", "an", "how", "why", "do", "does", "can", "in", "of", "to"}
        meaningful_words = query_words - stop_words
        
        if not meaningful_words:
            return []
            
        results = []
        for doc in self.documents:
            content = doc["content"].lower()
            doc_words = set(re.findall(r'\w+', content))
            
            score = 0.0
            
            # 1. Phrase matching (very strong)
            query_clean = re.sub(r'\s+', ' ', text_query.lower().strip())
            if len(query_clean) > 5 and query_clean in content:
                score += 2.0
                
            # 2. Lexical meaningful word overlap
            overlap = meaningful_words.intersection(doc_words)
            lexical_score = len(overlap) / float(len(meaningful_words))
            score += lexical_score
            
            # Penalize generic single-word hits
            if len(meaningful_words) == 1 and score < 1.5:
                # e.g., only "data" matched.
                score *= 0.1
                
            if score >= threshold:
                results.append({"doc": doc, "score": score})
                
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

# Global instance
rag_system = RAGCore()
