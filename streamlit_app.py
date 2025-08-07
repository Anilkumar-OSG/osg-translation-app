import streamlit as st
import pandas as pd
import re
import os
from datetime import datetime
import requests
from io import BytesIO

st.set_page_config(page_title="OSG Translation App", layout="wide")

# -----------------------------
# Load Logo (if available)
# -----------------------------
LOGO_PATH = "logo.png"
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=300)

st.title("OSG Translation App")

# -----------------------------
# Define constants
# -----------------------------
LANG_MODELS = {
    "Arabic (ar)": "Helsinki-NLP/opus-mt-en-ar",
    "Chinese (zh)": "Helsinki-NLP/opus-mt-en-zh",
    "Dutch (nl)": "Helsinki-NLP/opus-mt-en-nl",           
    "French (fr)": "Helsinki-NLP/opus-mt-en-fr",
    "German (de)": "Helsinki-NLP/opus-mt-en-de",          
    "Hindi (hi)": "Helsinki-NLP/opus-mt-en-hi",
    "Italian (it)": "Helsinki-NLP/opus-mt-en-it",         
    "Japanese (ja)": "staka/fugumt-en-ja",
    "Portuguese (pt)": "Helsinki-NLP/opus-mt-en-pt",     
    "Spanish (es)": "Helsinki-NLP/opus-mt-en-es"
}


COUNTRY_CODES = {"US", "UK", "CA", "DE", "FR", "IT", "JP", "CH", "IN"}

# -----------------------------
# Helper functions
# -----------------------------
def clean_text(text):
    text = str(text).strip()
    text = re.sub(r"^[\s\.\-•–]+", "", text)
    text = re.sub(r"[•–]{2,}", "-", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text

def should_skip_translation(text):
    return text.upper() in COUNTRY_CODES or re.fullmatch(r"[A-Z]{2,3}", text)

def split_preserve_segments(text):
    pattern = r"(<[^>]+>|</[^>]+>|\$\{[^}]+\}|\[pipe:[^\]]+\])"
    parts = re.split(pattern, text)
    segments = []
    for part in parts:
        if not part:
            continue
        if re.match(pattern, part):
            segments.append(('preserve', part))
        else:
            segments.append(('text', part))
    return segments

def translate_text_via_api(text, model_name):
    hf_token = st.secrets["HF_TOKEN"]
    api_url = f"https://api-inference.huggingface.co/models/{model_name}"
    headers = {"Authorization": f"Bearer {hf_token}"}
    payload = {"inputs": text}
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, list) and 'translation_text' in result[0]:
            return result[0]['translation_text']
        elif isinstance(result, dict) and 'error' in result:
            return f"[ERROR: {result['error']}]"
        return text
    except Exception as e:
        return f"[API ERROR: {e}]"

def translate_preserving_tags(text, model_name):
    segments = split_preserve_segments(text)
    to_translate = [clean_text(seg[1]) for seg in segments if seg[0] == 'text' and seg[1].strip()]

    if not to_translate:
        return text

    translations = []
    for chunk in to_translate:
        translated = translate_text_via_api(chunk, model_name)
        translations.append(translated)

    result = []
    trans_index = 0
    for typ, val in segments:
        if typ == 'text' and val.strip():
            result.append(translations[trans_index])
            trans_index += 1
        elif typ == 'preserve':
            if val.startswith("[pipe:") or val.startswith("${"):
                result.append(f" {val} ")
            else:
                result.append(val)

    joined = "".join(result)
    joined = re.sub(r'\s{2,}', ' ', joined)
    joined = re.sub(r'\s+(</?\w+[^>]*>)\s+', r' \1 ', joined)
    return joined.strip()

# -----------------------------
# Upload and language selection
# -----------------------------
st.header("1. Upload your Excel file")
uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    if df.shape[1] < 3:
        st.error("Your Excel must have at least 3 columns. Column C should contain English text.")
        st.stop()

    source = df.iloc[:, 2].astype(str)

    st.header("2. Select Target Languages")
    selected_langs = st.multiselect("Choose target languages:", options=list(LANG_MODELS.keys()))

    if selected_langs and st.button("Start Translation"):
        progress = st.progress(0)

        for idx, lang in enumerate(selected_langs):
            model_name = LANG_MODELS[lang]
            translated = []
            total = len(source)

            for i, text in enumerate(source):
                txt = clean_text(text)
                if should_skip_translation(txt):
                    translated.append(txt)
                elif txt.lower() == "yes":
                    translated.append("Ja" if lang == "German (de)" else "Oui" if lang == "French (fr)" else "Sí")
                elif txt.lower() == "no":
                    translated.append("Nein" if lang == "German (de)" else "Non" if lang == "French (fr)" else "No")
                else:
                    translated.append(translate_preserving_tags(txt, model_name))
                progress.progress(min(100, int(((idx + i / total) / len(selected_langs)) * 100)))

            df[lang] = translated

        # Save to Excel in memory
        output = BytesIO()
        now = datetime.now().strftime("%Y-%m-%d")
        file_basename = os.path.splitext(uploaded_file.name)[0]
        df.to_excel(output, index=False)
        st.success("Translation complete!")
        st.download_button(
            label="Download Translated Excel",
            data=output.getvalue(),
            file_name=f"{file_basename}_Translated_{now}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
