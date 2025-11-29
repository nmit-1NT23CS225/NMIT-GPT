from pipeline.load_to_db import supabase, fetch_all_faculty
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os
load_dotenv()
model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

def build_raw_text(row):
    return (
        f"{row.get('name', '')} is {row.get('designation', '')} in the {row.get('department', '')}. "
        f"They have {row.get('experience', '')} of experience and hold the qualifications: {row.get('qualification', '')}. "
        f"Their academic interests include: {row.get('interests', '')}. "
        f"They have taught subjects such as: {row.get('subjects_taught', '')}. "
        f"Achievements: {row.get('achievements', '')}. "
        f"Research contributions: {row.get('research', '')}. "
        f"Joining date: {row.get('joining_date', '')}. "
        f"Scholar ID: {row.get('scholar_id', '')}. "
        f"ORCID: {row.get('orcid_id', '')}. "
        f"LinkedIn: {row.get('linkedIn_id', '')}. "
        f"Contact email: {row.get('email', '')}."
    ).strip()

def chunk_text(text, max_chars=500):
    if not text or not text.strip():
        return []
    sentences = text.split(".")
    chunks, current = [], ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(current) + len(s) < max_chars:
            current += s + ". "
        else:
            chunks.append(current.strip())
            current = s + ". "

    if current.strip():
        chunks.append(current.strip())

    return chunks
def update_raw_text_in_db(faculty_id, raw_text):
    supabase.table("faculty_biodata").update(
        {"raw_text": raw_text}
    ).eq("faculty_id", faculty_id).execute()
def insert_embedding_with_metadata(faculty_id, chunk_id, chunk, vec, metadata):
    supabase.table("faculty_biodata_embeddings").insert({
        "faculty_id": faculty_id,
        "chunk_id": chunk_id,
        "chunk_text": chunk,
        "embedding": vec,
        "metadata": metadata
    }).execute()
def generate_chunk_embeddings():
    faculty_rows = fetch_all_faculty()

    for row in faculty_rows:
        faculty_id = row["faculty_id"]
        raw_text = build_raw_text(row)
        if not raw_text:
            print(f"No raw_text for faculty {faculty_id}")
            continue
        update_raw_text_in_db(faculty_id, raw_text)
        chunks = chunk_text(raw_text)
        if not chunks:
            print(f"No chunks for faculty {faculty_id}")
            continue

        metadata = {
            "faculty_id": faculty_id,
            "name": row.get("name"),
            "designation": row.get("designation"),
            "department": row.get("department"),
            "source": "auto_generated_raw_text"
        }
        # Embedding each chunk
        for idx, chunk in enumerate(chunks):
            vec = model.encode(chunk).tolist()
            insert_embedding_with_metadata(faculty_id, idx, chunk, vec, metadata)

        print(f"Embedded {len(chunks)} chunks for faculty {faculty_id}")

    print("Completed embedding process!")

if __name__ == "__main__":
    generate_chunk_embeddings()
