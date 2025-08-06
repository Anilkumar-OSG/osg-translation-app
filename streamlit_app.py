import streamlit as st
import pandas as pd
import re
import os
from datetime import datetime
from transformers import MarianMTModel, MarianTokenizer
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

def translate_preserving_tags(text, model, tokenizer):
    segments = split_preserve_segments(text)
    to_translate = [clean_text(seg[1]) for seg in segments if seg[0] == 'text' and seg[1].strip()]

    if not to_translate:
        return text

    try:
        inputs = tokenizer(to_translate, return_tensors="pt", padding=True, truncation=True)
        outputs = model.generate(**inputs, max_length=512, num_beams=4, early_stopping=True)
        translations = tokenizer.batch_decode(outputs, skip_special_tokens=True)
    except Exception as e:
        st.warning(f"Translation error: {e}")
        return text

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
            tokenizer = MarianTokenizer.from_pretrained(LANG_MODELS[lang])
            model = MarianMTModel.from_pretrained(LANG_MODELS[lang])
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
                    translated.append(translate_preserving_tags(txt, model, tokenizer))
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
