# retriever.py
from .db import get_supabase_client

supabase = get_supabase_client()

# Update these according to your teammate's DB schema
TABLE_NAME = "faculty_embeddings"
EMBED_COL = "embedding"
TEXT_COL = "content"
META_COLS = ["subject", "faculty_name"]  # Optional if metadata exists


def search_similar(embedding: list, top_k: int = 5):
    """
    Perform vector search using pgvector in Supabase.
    Returns a list of {content, metadata}
    """
    try:
        response = (
            supabase.rpc(
                "match_documents",  # name of RPC function in Supabase
                {"query_embedding": embedding, "match_count": top_k}
            ).execute()
        )

        results = response.data

        docs = []
        for row in results:
            docs.append({
                "content": row.get(TEXT_COL, ""),
                "metadata": {key: row.get(key) for key in META_COLS}
            })

        return docs

    except Exception as e:
        print("Error during vector search:", e)
        return []
