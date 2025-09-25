import streamlit as st
import requests
import base64
from PIL import Image
import io
import os
import json
import re

# --------- REDIS/API KEY SUPPORT (optional, can simplify if not using redis) ---------
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

# --------- SYSTEM: LOAD PROMPT TEMPLATE FROM FILE ---------
def load_prompt_template():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(script_dir, "portfolio_reviewer_1.1.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
    return prompt_template

# --------- IMAGE SIZE CHECK ---------
MAX_SIZE_MB = 1
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

def check_image_size(image_file):
    if image_file is not None and image_file.size > MAX_SIZE_BYTES:
        st.error(f"Image file '{image_file.name}' is too large ({image_file.size/1024/1024:.2f}MB). Limit is {MAX_SIZE_MB}MB.")
        return False
    return True

# --------- IMAGE TO BASE64 ---------
def image_to_base64(image_file):
    image = Image.open(image_file)
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    return img_b64

# --------- OPENROUTER MULTIMODAL GPT-4o CALL ---------
def call_openrouter_multimodal(api_key, image_b64_list, prompt, model="openai/gpt-4o", temperature=0):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "your-app-or-email",  # Replace with your app or email as required by OpenRouter
        "Content-Type": "application/json"
    }
    content = [{"type": "text", "text": prompt}]
    for img_b64 in image_b64_list:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"}
        })
    data = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "temperature": temperature
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=data,
        timeout=120
    )
    if response.ok:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error: {response.status_code}\n{response.text}"

# --------- RENDER AI RESPONSE (robust JSON extraction) ---------
def render_ai_review(json_str):
    # Remove markdown code block if present
    match = re.search(r"```json\s*(.*?)```", json_str, re.DOTALL | re.IGNORECASE)
    if not match:
        match = re.search(r"```(.*?)```", json_str, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    try:
        response = json.loads(json_str)
    except Exception:
        st.error("Could not parse AI response as JSON.")
        st.text_area("Raw AI response", json_str, height=200)
        return

    checklist = response.get("checklist", [])
    summary = response.get("summary", "")
    recommendations = response.get("action_recommendations", [])
    symbol_recs_table_md = response.get("symbol_recommendations_table", "")

    st.subheader("Checklist Review")
    for section in checklist:
        st.markdown(f"**{section.get('section', '')}**")
        for item in section.get("items", []):
            status = item["status"].lower()
            if status == "pass":
                status_icon = "✅"
            elif status == "fail":
                status_icon = "❌"
            else:
                status_icon = "❓"
            st.markdown(f"- {status_icon} **{item['item']}**: {item['comment']}")
        st.markdown("---")

    st.subheader("Summary")
    st.info(summary)

    st.subheader("Action Recommendations")
    for rec in recommendations:
        st.markdown(f"- {rec}")

    # Show only the Markdown version of the per-symbol recommendation table
    if symbol_recs_table_md:
        st.subheader("Per-Symbol Recommendation Table")
        st.markdown(symbol_recs_table_md, unsafe_allow_html=True)

# --------- STREAMLIT UI ---------
st.set_page_config(page_title="Trading Portfolio AI Review (GPT-4o Multimodal)", layout="wide")
st.title("📊 Trading Portfolio AI Review (GPT-4o Multimodal)")

st.markdown(
    f"""
**Image size limit:** {MAX_SIZE_MB}MB per image.

1. Upload your **Performance Monitor** images (History and/or Open Trades).
2. Click **Process with AI** to have GPT-4o extract the tables and review your portfolio.
3. See the AI's checklist review, summary, per-symbol recommendations, and more.
    """
)

col1, col2 = st.columns(2)
with col1:
    history_img = st.file_uploader("Upload History Trades Image", type=["png", "jpg", "jpeg"], key="history")
with col2:
    open_img = st.file_uploader("Upload Open Trades Image", type=["png", "jpg", "jpeg"], key="open")

# ---- Image size check ----
if history_img and not check_image_size(history_img):
    history_img = None
if open_img and not check_image_size(open_img):
    open_img = None

api_key = st.text_input(
    "OpenRouter API key",
    value=get_open_router_api_key() or "",
    type="password"
)

prompt_template = load_prompt_template()

uploaded_imgs = []
img_labels = []
if history_img:
    uploaded_imgs.append(history_img)
    img_labels.append("History")
if open_img:
    uploaded_imgs.append(open_img)
    img_labels.append("Open Trades")

for label, img in zip(img_labels, uploaded_imgs):
    st.image(img, caption=f"{label} Screenshot", use_container_width=True)

# Session state for last response
if "last_response" not in st.session_state:
    st.session_state["last_response"] = None

submit = st.button("Process with AI", disabled=not (uploaded_imgs and api_key and prompt_template))

if submit:
    with st.spinner("Sending image(s) to OpenRouter GPT-4o..."):
        img_b64_list = [image_to_base64(img) for img in uploaded_imgs]
        # Set temperature=0 for deterministic output
        ai_response_text = call_openrouter_multimodal(api_key, img_b64_list, prompt_template, temperature=0)
        st.session_state["last_response"] = ai_response_text
    st.markdown("---")
    st.subheader("AI Portfolio Review")
    render_ai_review(st.session_state["last_response"])
elif st.session_state["last_response"]:
    st.markdown("---")
    st.subheader("AI Portfolio Review")
    render_ai_review(st.session_state["last_response"])