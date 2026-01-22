import os
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

from pipeline.load_to_db import (
    fetch_all_faculty,
    fetch_all_labs,
    insert_embeddings,
    fetch_embedded_faculty_ids,
    fetch_embedded_lab_ids
)

load_dotenv()
model = SentenceTransformer(os.getenv("EMBEDDING_MODEL"))
def build_lab_chunks(row):
    def has_value(val):
        return val is not None and str(val).strip() != ""

    chunks = []

    lab_name = row.get("lab_name", "The lab")
    room = row.get("room_number")
    total = row.get("no_of_computers")
    brands = row.get("brand_computer_counts")
    config = row.get("configuration_summary")
    overview_parts = []

    if has_value(lab_name):
        overview_parts.append(f"The {lab_name}")

    if has_value(room):
        overview_parts.append(f"is located in Room {room}")
    else:
        overview_parts.append("is located within the institute")

    if has_value(total):
        overview_parts.append(f"and is equipped with {total} computers")

    if overview_parts:
        chunks.append((
            "01_overview",
            " ".join(overview_parts) + "."
        ))
    if isinstance(brands, dict) and brands:
        brand_text = ", ".join(
            f"{brand} systems ({count})"
            for brand, count in brands.items()
            if has_value(brand) and count
        )

        if has_value(brand_text):
            if has_value(total):
                chunks.append((
                    "02_brands",
                    f"Out of {total} computers, the lab has {brand_text}."
                ))
            else:
                chunks.append((
                    "02_brands",
                    f"The lab has a brand-wise distribution of {brand_text}."
                ))

    if has_value(config) and has_value(total):
        chunks.append((
            "03_configuration",
            f"The lab is equipped with {total} computers featuring {config}."
        ))

    return chunks


def build_faculty_chunks(row):
    def join_list(val):
        if isinstance(val, list):
            return ", ".join(v for v in val if v)
        return ""

    def has_value(val):
        return val is not None and str(val).strip() != ""

    chunks = []
    profile_parts = []

    if has_value(row.get("name")):
        profile_parts.append(row["name"])

    if has_value(row.get("designation")):
        profile_parts.append(f"is working as {row['designation']}")

    if has_value(row.get("department")):
        profile_parts.append(f"in the Department of {row['department']}")

    qualifications = join_list(row.get("educational_qualifications"))
    if has_value(qualifications):
        profile_parts.append(f"with qualifications in {qualifications}")

    experience = join_list(row.get("past_experience"))
    if has_value(experience):
        profile_parts.append(f"with professional experience in {experience}")

    if profile_parts:
        chunks.append((
            "01_profile",
            " ".join(profile_parts) + "."
        ))
    interests = join_list(row.get("areas_of_interest"))
    if has_value(interests):
        chunks.append((
            "02_interests",
            f"Areas of academic and research interest include {interests}."
        ))
    subjects = join_list(row.get("subjects_taught"))
    if has_value(subjects):
        chunks.append((
            "03_subjects",
            f"Subjects taught include {subjects}."
        ))
    achievements = join_list(row.get("achievements"))
    if has_value(achievements):
        chunks.append((
            "04_achievements",
            f"Notable achievements include {achievements}."
        ))
    research = row.get("research")
    if has_value(research):
        chunks.append((
            "05_research",
            f"Research work focuses on {research.strip()}."
        ))

    return chunks

def embed_faculty():
    faculty_rows = fetch_all_faculty()
    already_embedded = fetch_embedded_faculty_ids()
    records = []

    for row in faculty_rows:
        faculty_id = row["faculty_id"]

        if faculty_id in already_embedded:
            continue

        for idx, (chunk_type, text) in enumerate(build_faculty_chunks(row)):
            vec = model.encode(text).tolist()

            records.append({
                "source_type": "faculty_biodata",
                "source_id": faculty_id,
                "chunk_type": chunk_type,
                "chunk_index": idx,
                "raw_text": text,
                "metadata": {
                    "entity": "faculty",
                    "name": row.get("name"),
                    "department": row.get("department")
                },
                "embedding": vec
            })

    if records:
        insert_embeddings(records)
        print(f"Embedded {len(records)} faculty chunks")
    else:
        print("ℹNo new faculty chunks to embed")


def embed_labs():
    lab_rows = fetch_all_labs()
    already_embedded = fetch_embedded_lab_ids()
    records = []

    for row in lab_rows:
        if row["lab_id"] in already_embedded:
            continue

        for idx, (chunk_type, text) in enumerate(build_lab_chunks(row)):
            vec = model.encode(text).tolist()

            records.append({
                "source_type": "lab",
                "source_id": row["lab_id"],
                "chunk_type": chunk_type,
                "chunk_index": idx,
                "raw_text": text,
                "metadata": {
                    "entity": "lab",
                    "lab_name": row["lab_name"],
                    "room_number": row["room_number"]
                },
                "embedding": vec
            })

    if records:
        insert_embeddings(records)
        print(f"Embedded {len(records)} lab chunks")
    else:
        print("No new lab chunks to embed")
