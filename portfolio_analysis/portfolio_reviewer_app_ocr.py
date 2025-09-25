import streamlit as st
from PIL import Image, ImageOps
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import pandas as pd
import numpy as np
import requests
import json
import os
import re

# --------- SYSTEM: LOAD PROMPT TEMPLATE FROM FILE ---------
def load_prompt_template():
    prompt_path = os.path.join(os.path.dirname(__file__), "portfolio_reviewer_1.0.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
    return prompt_template

# --------- REDIS/API KEY SUPPORT (edit Redis connection if needed) ---------
def get_open_router_api_key():
    try:
        import redis
        r = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            decode_responses=True
        )
    except Exception:
        r = None

    key = st.session_state.get("open_router_api_key")
    if key:
        return key
    username = st.session_state.get("username")
    if username and r:
        val = r.get(f"user:{username}:open_router_api_key")
        if val:
            return val
    return None

# --------- PIL-ONLY PREPROCESSING ---------
def pil_preprocess(image, threshold=180):
    # Convert to grayscale
    image = ImageOps.grayscale(image)
    # Simple binarization (threshold)
    image = image.point(lambda x: 0 if x < threshold else 255, '1')
    return image

# --------- OCR AND TABLE UTILITY ---------
def ocr_image_to_table(image_file, tesseract_config, lang="eng", preprocess=True, threshold=180, show_preprocessed=True):
    image = Image.open(image_file)
    if preprocess:
        image = pil_preprocess(image, threshold=threshold)
    if show_preprocessed:
        st.image(image, caption="Preprocessed for OCR (PIL)", use_column_width=True)
    raw_text = pytesseract.image_to_string(image, lang=lang, config=tesseract_config)
    # Try to split text into rows and columns
    lines = [line for line in raw_text.split("\n") if line.strip()]
    if not lines or len(lines) < 2:
        return pd.DataFrame(), raw_text
    # Use multiple spaces or tabs to split columns
    header = re.split(r'\s{2,}|\t', lines[0].strip())
    rows = []
    for line in lines[1:]:
        cells = re.split(r'\s{2,}|\t', line.strip())
        if len(cells) == len(header):
            rows.append(cells)
        else:
            # fallback: split on single spaces
            cells = line.strip().split()
            if len(cells) == len(header):
                rows.append(cells)
    if rows and header:
        df = pd.DataFrame(rows, columns=header)
        return df, raw_text
    else:
        return pd.DataFrame(), raw_text

def df_to_markdown_table(df):
    if df.empty:
        return ""
    return df.to_markdown(index=False)

# --------- OPENROUTER API CALL ---------
def call_openrouter_api(prompt, api_key, model="gpt-4o"):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        try:
            ai_content = result["choices"][0]["message"]["content"]
        except Exception:
            ai_content = "Failed to parse AI response."
        return ai_content
    else:
        return f"Error from OpenRouter: {response.status_code} - {response.text}"

# --------- RENDER AI RESPONSE ---------
def render_ai_review(json_str):
    try:
        response = json.loads(json_str)
    except Exception:
        st.error("Could not parse AI response as JSON.")
        st.text_area("Raw AI response", json_str, height=200)
        return

    checklist = response.get("checklist", [])
    summary = response.get("summary", "")
    recommendations = response.get("action_recommendations", [])

    st.subheader("Checklist Review")
    for section in checklist:
        st.markdown(f"**{section.get('section', '')}**")
        for item in section.get("items", []):
            status_icon = "✅" if item["status"].lower() == "pass" else "❌"
            st.markdown(f"- {status_icon} **{item['item']}**: {item['comment']}")
        st.markdown("---")

    st.subheader("Summary")
    st.info(summary)

    st.subheader("Action Recommendations")
    for rec in recommendations:
        st.markdown(f"- {rec}")

# --------- STREAMLIT UI ---------
st.set_page_config(page_title="Trading Portfolio AI Review", layout="wide")
st.title("📊 Trading Portfolio AI Review")

st.markdown(
    """
1. Upload your **Performance Monitor** images (History and Open Trades).
2. OCR extracts table text and displays as editable table (you can correct).
3. Click **Process with AI** to review your portfolio.
4. See the AI's checklist review, summary, and recommendations.
    """
)

col1, col2 = st.columns(2)
with col1:
    history_img = st.file_uploader("Upload History Trades Image", type=["png", "jpg", "jpeg"], key="history")
with col2:
    open_img = st.file_uploader("Upload Open Trades Image", type=["png", "jpg", "jpeg"], key="open")

# --------- OCR CONFIGS UI (PIL-only) ---------
st.sidebar.header("OCR Debug & Config")
tess_lang = st.sidebar.selectbox(
    "Tesseract Language",
    options=["eng", "chi_sim", "chi_tra"],
    index=0,
    help="Choose OCR language: English, Simplified Chinese, or Traditional Chinese."
)
tess_psm = st.sidebar.selectbox(
    "Tesseract PSM (Page Segmentation Mode)",
    options=[6, 4, 11, 12],
    index=0,
    help="Try different PSM modes for best table extraction."
)
tess_preprocess = st.sidebar.checkbox(
    "Enable PIL Image Preprocessing", value=True,
    help="Convert to grayscale and apply threshold for improved OCR."
)
tess_threshold = st.sidebar.slider(
    "Binarization Threshold", min_value=100, max_value=250, value=180, step=1,
    help="Adjust threshold for binarization (lower = darker, higher = lighter)."
)
tess_config_str = f'--oem 3 --psm {tess_psm}'

history_df, open_df = pd.DataFrame(), pd.DataFrame()
history_raw, open_raw = "", ""

if history_img:
    history_df, history_raw = ocr_image_to_table(
        history_img, tess_config_str, lang=tess_lang,
        preprocess=tess_preprocess, threshold=tess_threshold, show_preprocessed=True
    )
    st.text_area("Raw OCR result (History)", history_raw, height=150)
if open_img:
    open_df, open_raw = ocr_image_to_table(
        open_img, tess_config_str, lang=tess_lang,
        preprocess=tess_preprocess, threshold=tess_threshold, show_preprocessed=True
    )
    st.text_area("Raw OCR result (Open)", open_raw, height=150)

st.markdown("#### History Trades Table (editable)")
if not history_df.empty:
    history_df = st.data_editor(history_df, num_rows="dynamic", key="history_table")
    history_table_md = df_to_markdown_table(history_df)
else:
    history_table_md = st.text_area("History table (Markdown)", "", height=200)

st.markdown("#### Open Trades Table (editable)")
if not open_df.empty:
    open_df = st.data_editor(open_df, num_rows="dynamic", key="open_table")
    open_table_md = df_to_markdown_table(open_df)
else:
    open_table_md = st.text_area("Open trades table (Markdown)", "", height=200)

api_key = st.text_input("OpenRouter API key", value=get_open_router_api_key() or "", type="password")

prompt_template = load_prompt_template()

if st.button("Process with AI", disabled=not (api_key and prompt_template and history_table_md and open_table_md)):
    with st.spinner("Calling AI reviewer..."):
        prompt = prompt_template.replace("{history_table}", history_table_md).replace("{open_table}", open_table_md)
        ai_response_text = call_openrouter_api(prompt, api_key)
        st.markdown("### AI Portfolio Review")
        render_ai_review(ai_response_text)