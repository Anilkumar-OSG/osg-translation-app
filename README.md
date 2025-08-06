# 🌐 OSG Translation App (v1.0) – Streamlit Edition

Welcome to the web-based version of the OSG Translation App!

This version uses **Streamlit** as the frontend, and performs translation using Hugging Face’s **MarianMT** models.

---

## 📁 Included Files

- `streamlit_app.py` – Main app script (or `OSG_Translation_Streamlit_App_v1.0.py`)
- `logo.png` – Optional logo displayed at the top of the app
- `README.md` – You're reading it!
- `requirements.txt` – Required Python libraries for deployment

---

## 🚀 Features

- Translate Excel files into **10 languages**:
  - Arabic, Chinese, Dutch, French, German, Hindi, Italian, Japanese, Portuguese, Spanish
- Preserves dynamic tags:
  - `[pipe:...]`, `${...}`, and HTML tags like `<b>`, `<i>`, `<u>`
- Supports **batch translation** from Excel files
- Automatically saves translated files with date + language appended
- Runs fully in-browser – no local installation needed
- First-time use will download models (~50–100MB), then works offline on server

---

## 📥 How to Use (Locally or on Streamlit Cloud)

### ✅ Online (via Streamlit Cloud)
1. Upload all files to a GitHub repository.
2. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud).
3. Click **New app**, select your GitHub repo.
4. Use `streamlit_app.py` as the main entry point.
5. The app will launch in the browser.

### ✅ Locally (for internal testing)
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
