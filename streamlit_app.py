import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import os
import re
from datetime import datetime
from transformers import MarianMTModel, MarianTokenizer
import threading

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl.worksheet.header_footer")


# Language Models
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
PIPE_PATTERN = re.compile(r"(\[pipe:[^\]]+\])")
DOLLAR_PATTERN = re.compile(r"(\$\{[^\}]+\})")
HTML_TAG_PATTERN = re.compile(r"(<[^>]+>)")

# UI Setup
root = tk.Tk()
root.title("OSG Translation App")
root.geometry("1100x700")
root.configure(bg="#f6f6f6")
theme_blue = "#1177dd"
theme_font = ("Helvetica", 12)

header_frame = tk.Frame(root, bg=theme_blue, height=90)
header_frame.pack(fill="x")

try:
    from PIL import Image, ImageTk
    logo_img = Image.open("logo.png").resize((250, 80))
    logo_photo = ImageTk.PhotoImage(logo_img)
    tk.Label(header_frame, image=logo_photo, bg=theme_blue).pack(side="left", padx=10)
except Exception as e:
    print("Logo error:", e)

tk.Label(header_frame, text="OSG Translation App", font=("Helvetica", 20, "bold"),
         fg="white", bg=theme_blue).place(relx=0.5, rely=0.5, anchor="center")

file_path = tk.StringVar()

def browse_file():
    path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
    if path:
        file_path.set(path)
        file_label.config(text=os.path.basename(path), fg="black")

tk.Label(root, text="Step 1: Upload your Excel file", font=("Helvetica", 14, "bold"), bg="#f6f6f6").pack(pady=(20, 5))
tk.Button(root, text="Browse Excel File", command=browse_file, font=theme_font, bg="#1177dd", fg="white", width=20).pack()
file_label = tk.Label(root, text="No file selected", fg="red", bg="#f6f6f6")
file_label.pack(pady=(5, 10))

# Language Selection
tk.Label(root, text="Step 2: Select Target Languages", font=("Helvetica", 14, "bold"), bg="#f6f6f6").pack()
checkbox_frame = tk.Frame(root, bg="#f6f6f6")
checkbox_frame.pack()
lang_vars = {}
cols = 3
for i, (lang, _) in enumerate(LANG_MODELS.items()):
    var = tk.BooleanVar()
    chk = tk.Checkbutton(checkbox_frame, text=lang, variable=var, bg="#f6f6f6", font=theme_font)
    chk.grid(row=i // cols, column=i % cols, padx=30, pady=3)
    lang_vars[lang] = var

# Progress Bar
progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(root, orient="horizontal", length=500, mode="determinate", variable=progress_var)
progress_label = tk.Label(root, text="0%", bg="#f6f6f6", font=("Helvetica", 10))
progress_bar.pack(pady=(20, 0))
progress_label.pack(pady=(0, 10))

stop_translation = False

# Cleaning & Tag Preservation
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
        if re.match(r"<[^>]+>|</[^>]+>|\$\{[^}]+\}|\[pipe:[^\]]+\]", part):
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
        print("Translation error:", e)
        return text

    # Reconstruct text with added spacing for dynamic tags
    result = []
    trans_index = 0
    for typ, val in segments:
        if typ == 'text' and val.strip():
            result.append(translations[trans_index])
            trans_index += 1
        elif typ == 'preserve':
            # Add space around dynamic content
            if val.startswith("[pipe:") or val.startswith("${"):
                result.append(f" {val} ")
            else:
                result.append(val)

    joined = "".join(result)

    # Clean up extra spacing around HTML tags and between words
    joined = re.sub(r'\s{2,}', ' ', joined)
    joined = re.sub(r'\s+(</?\w+[^>]*>)\s+', r' \1 ', joined)
    return joined.strip()



def run_translation():
    global stop_translation
    path = file_path.get()
    if not path:
        messagebox.showerror("Error", "Please upload an Excel file.")
        return

    try:
        df = pd.read_excel(path, engine='openpyxl')
    except Exception as e:
        messagebox.showerror("Error", f"Error reading Excel file: {e}")
        return

    source = df.iloc[:, 2].astype(str)
    selected_langs = [lang for lang, var in lang_vars.items() if var.get()]
    if not selected_langs:
        messagebox.showerror("Error", "Please select at least one target language.")
        return

    for lang in selected_langs:
        if stop_translation:
            break
        try:
            tokenizer = MarianTokenizer.from_pretrained(LANG_MODELS[lang])
            model = MarianMTModel.from_pretrained(LANG_MODELS[lang])
        except Exception as e:
            messagebox.showerror("Error", f"Model load failed for {lang}:\n{str(e)}")
            continue

        translated = []
        total = len(source)
        for i, text in enumerate(source):
            if stop_translation:
                break
            txt = clean_text(text)
            if should_skip_translation(txt):
                translated.append(txt)
            elif txt.lower() == "yes":
                translated.append("Ja" if lang == "German (de)" else "Oui" if lang == "French (fr)" else "Sí")
            elif txt.lower() == "no":
                translated.append("Nein" if lang == "German (de)" else "Non" if lang == "French (fr)" else "No")
            else:
                translated.append(translate_preserving_tags(txt, model, tokenizer))
            pct = int((i + 1) / total * 100)
            progress_var.set(pct)
            progress_label.config(text=f"{pct}%")
            root.update_idletasks()

        df[lang] = translated
        now = datetime.now().strftime("%Y-%m-%d")
        outname = f"{os.path.splitext(os.path.basename(path))[0]}_Translated_{lang.split()[0]}_{now}.xlsx"
        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=outname)
        if save_path:
            df.to_excel(save_path, index=False)

    progress_var.set(100)
    progress_label.config(text="100%")
    if not stop_translation:
        messagebox.showinfo("Done", "Translation complete.")

def start_translation():
    global stop_translation
    stop_translation = False
    threading.Thread(target=run_translation).start()

def cancel_translation():
    global stop_translation
    stop_translation = True
    messagebox.showinfo("Cancelled", "Translation cancelled.")

# Buttons
btn_frame = tk.Frame(root, bg="#f6f6f6")
btn_frame.pack(pady=20)
tk.Button(btn_frame, text="Start Translation", command=start_translation, font=("Helvetica", 12, "bold"), bg="green", fg="white", width=18).grid(row=0, column=0, padx=10)
tk.Button(btn_frame, text="Cancel", command=cancel_translation, font=("Helvetica", 12, "bold"), bg="orange", fg="black", width=12).grid(row=0, column=1, padx=10)
tk.Button(btn_frame, text="Close App", command=root.destroy, font=("Helvetica", 12, "bold"), bg="darkred", fg="white", width=12).grid(row=0, column=2, padx=10)

root.mainloop()
