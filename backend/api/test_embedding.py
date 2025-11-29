from RAG_ENGINE.src.embedder import embed_query
import json

vec = embed_query("dummy test question")
print(len(vec))
print(json.dumps(vec))
