import pandas as pd
import re

def clean_date(value):
    if pd.isna(value) or value == "":
        return None
    try:
        return pd.to_datetime(value).date().isoformat()
    except Exception:
        return None


def to_array(value):
    if pd.isna(value) or value == "":
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


def normalize_columns(df):
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(".", "", regex=False)
    )
    return df


def extract_room_number(text):
    match = re.search(r"room\s*(\d+)", str(text).lower())
    return match.group(1) if match else None


def clean_text(text):
    if pd.isna(text):
        return ""
    text = str(text)
    replacements = {
        ";": ". ",
        ":": " ",
        "@": " at ",
        "\n": " "
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return re.sub(r"\s+", " ", text).strip()
def clean_nan(value):
    try:
        import pandas as pd
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value
import re

def clean_lab_configuration(config_list):
    if not config_list:
        return None, None

    unique = list(dict.fromkeys(config_list))
    text = " ".join(unique)

    match = re.search(r"no of computers\s*(\d+)", text.lower())
    computer_count = int(match.group(1)) if match else None

    text = re.sub(r"no of computers\s*\d+\.?", "", text, flags=re.IGNORECASE)

    text = " ".join(text.split())

    return text.strip(), computer_count
