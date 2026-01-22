
import pandas as pd
from pipeline.utils import (
    clean_date,
    to_array,
    normalize_columns,
    extract_room_number,
    clean_text,
    clean_nan
)
def extract_faculty_from_excel(filepath):
    df = pd.read_excel(filepath)
    rows = []

    for _, row in df.iterrows():
        rows.append({
            "name": clean_nan(row.get("name")),
            "designation": clean_nan(row.get("designation")),
            "department": clean_nan(row.get("department")),

            "email": to_array(row.get("email")),
            "educational_qualifications": to_array(row.get("qualification")),
            "past_experience": to_array(row.get("experience")),
            "areas_of_interest": to_array(row.get("interests")),
            "subjects_taught": to_array(row.get("subjects_taught")),
            "achievements": to_array(row.get("achievements")),

            "scholar_id": to_array(row.get("scholar_id")),
            "orcid_id": to_array(row.get("orcid_id")),
            "linkedin_id": to_array(row.get("linkedIn_id")),

            "research": clean_nan(row.get("research")),
            "joining_date": clean_date(row.get("joining_date"))
        })

    return rows
def extract_labs_from_excel(filepath):
    df = pd.read_excel(filepath)
    df = normalize_columns(df)

    labs = {}

    for _, row in df.iterrows():
        lab_name = row["lab name"]
        room_number = extract_room_number(lab_name)

        brand = str(row.get("computer brand", "")).strip()
        count = int(row.get("no of computers", 0))
        config = clean_text(row.get("total details"))

        if lab_name not in labs:
            labs[lab_name] = {
                "lab_name": lab_name,
                "room_number": room_number,
                "no_of_computers": 0,
                "brand_computer_counts": {},
                "configuration_summary": []
            }

        if brand:
            labs[lab_name]["brand_computer_counts"][brand] = (
                labs[lab_name]["brand_computer_counts"].get(brand, 0) + count
            )

        labs[lab_name]["no_of_computers"] += count

        if config:
            labs[lab_name]["configuration_summary"].append(config)

    from pipeline.utils import clean_lab_configuration

    final_labs = []

    for lab in labs.values():
        clean_config, extracted_count = clean_lab_configuration(
            lab["configuration_summary"]
        )

        if extracted_count:
            lab["no_of_computers"] = extracted_count

        lab["configuration_summary"] = clean_config
        final_labs.append(lab)

    return final_labs

