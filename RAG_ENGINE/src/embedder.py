# embedder.py
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

EMBED_MODEL = "text-embedding-3-small"

def embed_query(query: str):
    """
    Generate dense embedding for a user query text.
    Returns list[float] embedding vector
    """
    try:
        response = client.embeddings.create(
            model=EMBED_MODEL,
            input=query
        )
        return response.data[0].embedding

    except Exception as e:
        print("Error generating embedding:", e)
        return None


if __name__ == "__main__":
    print(embed_query("Hello world!"))
