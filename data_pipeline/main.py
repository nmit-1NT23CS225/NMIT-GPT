from pipeline.extract_text import extract_faculty_data
from pipeline.load_to_db import insert_faculty
from pipeline.chunk_and_embed import generate_chunk_embeddings

FILE_PATH = r"Copy of faculty_template_full(1).xlsx"

def run_pipeline():
    print("\nSTEP 1: Extracting data from Excel...")
    faculty_list = extract_faculty_data(FILE_PATH)
    print(f"Extracted {len(faculty_list)} faculty records.")

    print("\nSTEP 2: Inserting faculty into Supabase...")
    for faculty in faculty_list:
        insert_faculty(faculty)
    print("Faculty insert complete.")

    print("\nSTEP 3: Generating raw_text + chunking + embeddings...")
    generate_chunk_embeddings()

    print("\nPipeline Completed Successfully!")

if __name__ == "__main__":
    run_pipeline()
