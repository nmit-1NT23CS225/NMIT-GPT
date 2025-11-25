# embedder.py
from sentence_transformers import SentenceTransformer

# Load MPNet model for local embeddings
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

def embed_query(query: str):
    """
    Generate dense embedding for a user query text using MPNet-base-v2.
    Returns list[float] embedding vector
    """
    try:
        embedding = model.encode(query).tolist()
        return embedding
    except Exception as e:
        print("Embedding error:", e)
        return None
vec = embed_query("test")
print(len(vec))


#if __name__ == "__main__":
   # print(embed_query("Hello world!"))
