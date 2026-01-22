import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


def insert_faculty(rows):
    """
    Insert NEW faculty rows only.
    Assumes faculty_id is already generated and unique.
    """
    if rows:
        supabase.table("faculty_biodata").insert(rows).execute()


def fetch_all_faculty():
    return supabase.table("faculty_biodata").select("*").execute().data


def fetch_faculty_ids():
    data = (
        supabase
        .table("faculty_biodata")
        .select("faculty_id")
        .execute()
        .data
    )
    return {row["faculty_id"] for row in data}


def fetch_embedded_faculty_ids():
    """
    Returns faculty_ids that already have embeddings
    """
    data = (
        supabase
        .table("unified_embeddings")
        .select("source_id")
        .eq("source_type", "faculty_biodata")
        .execute()
        .data
    )
    return {row["source_id"] for row in data}



def insert_labs(rows):
    """
    Insert labs only once.
    Assumes lab_id is already generated.
    """
    if rows:
        supabase.table("lab_infrastructure").insert(rows).execute()


def fetch_all_labs():
    return supabase.table("lab_infrastructure").select("*").execute().data


def fetch_embedded_lab_ids():
    """
    Returns lab_ids that already have embeddings
    """
    data = (
        supabase
        .table("unified_embeddings")
        .select("source_id")
        .eq("source_type", "lab")
        .execute()
        .data
    )
    return {row["source_id"] for row in data}



def insert_embeddings(rows, batch_size=100):
    """
    Batch insert embeddings to avoid Supabase limits
    """
    for i in range(0, len(rows), batch_size):
        supabase.table("unified_embeddings").insert(
            rows[i:i + batch_size]
        ).execute()
