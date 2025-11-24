import os
from dotenv import load_dotenv
load_dotenv()

POSTGRES_CONN = os.getenv("POSTGRES_CONN")  # connection string from Supabase

TOP_K = 3

# LLM
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-4o-mini"
