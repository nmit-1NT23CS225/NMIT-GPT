from data_pipeline.load_to_db import supabase
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os
import ast   
model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
def chunk_text(text, max_chars=500):
    if not text or text.strip() == "":
        return []
    text = text.strip()
    sentences = text.split(".")
    chunks = []
    current = ""
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
def fetch_all_faculty():
    result = supabase.table("faculty_biodata").select(
        "faculty_id, raw_text, name, designation, department"
    ).execute()

    return result.data
def insert_embedding_with_metadata(faculty_id, chunk_id, text, vec, metadata):
    supabase.table("faculty_biodata_embeddings").insert({
        "faculty_id": faculty_id,
        "chunk_id": chunk_id,
        "chunk_text": text,
        "embedding": vec,
        "metadata": metadata
    }).execute()
def generate_chunk_embeddings():
    faculty_rows = fetch_all_faculty()
    for row in faculty_rows:
        faculty_id = row["faculty_id"]
        raw_text_list = row.get("raw_text")
        if isinstance(raw_text_list, str):
            try:
                raw_text_list = ast.literal_eval(raw_text_list)
            except Exception as e:
                print(f"❌ Failed to parse raw_text for faculty {faculty_id}: {raw_text_list}")
                continue
        if not raw_text_list or raw_text_list == [""] or raw_text_list == []:
            print(f"⚠️ Skipping faculty {faculty_id}: raw_text is empty")
            continue
        raw_text = raw_text_list[0].strip()
        chunks = chunk_text(raw_text, max_chars=500)
        if not chunks:
            print(f"⚠️ No valid chunks for faculty {faculty_id}")
            continue
        metadata = {
            "faculty_id": faculty_id,
            "name": row.get("name"),
            "designation": row.get("designation"),
            "department": row.get("department"),
            "source": "raw_text"
        }
        for idx, chunk in enumerate(chunks):
            vec = model.encode(chunk).tolist()
            insert_embedding_with_metadata(faculty_id, idx, chunk, vec, metadata)
        print(f"✅ Stored {len(chunks)} chunks for faculty {faculty_id}")
    print("🎉 All chunk embeddings + metadata stored successfully!")

if __name__ == "__main__":
    generate_chunk_embeddings()

