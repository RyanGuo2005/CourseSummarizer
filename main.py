from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from fpdf import FPDF
from pypdf import PdfReader
from datetime import date
import re
import streamlit as st
import time
import json

# ==============================================================
# CONSTANTS / METHODS
# ==============================================================
PROMPT = """
Please summarize this pdf lesson into concise bullet points, highlighting the key concepts and important details. 
The summary should be clear and easy to understand, suitable for quick review and study.
If possible, split up by lesson sections, and include any important formulas, definitions, or examples mentioned in the text.
Mention how to solve any problems or exercises included in the lesson, and provide step-by-step explanations if applicable.
"""


def save_course_history(course_name):
    if st.session_state.summary or st.session_state.messages:
        safe_course_name = (
            "".join([c for c in course_name if c.isalnum() or c in (" ", "_")])
            .strip()
            .replace(" ", "_")
        )
        filename = f"{safe_course_name}_history.json"

        course_data = {
            "course_name": course_name,
            "summary": st.session_state.summary,
            "messages": st.session_state.messages,
            "date": str(date.today()),
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(course_data, f, ensure_ascii=False, indent=4)
        st.sidebar.success(f"Course '{course_name}' saved successfully!")
        return True, filename
    else:
        st.sidebar.warning("No summary or messages to save for this course.")
    return False, None


# ==============================================================
# Retrieve API key and initialize client
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

# Load current history of summaries from a JSON file
try:
    with open("history.json", "r", encoding="utf-8") as f:
        chat_history = json.load(f)
except FileNotFoundError:
    chat_history = []

# ==============================================================
# Initialize Streamlit app
st.title("Lesson Summarizer")

# 1. Initialize the Client in Session State
if "genai_client" not in st.session_state:
    st.session_state.genai_client = genai.Client(api_key=API_KEY)

# 2. Initialize the Chat Session using the stored client
if "chat_session" not in st.session_state:
    st.session_state.chat_session = st.session_state.genai_client.chats.create(
        model="gemini-2-flash", history=chat_history
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

if "summary" not in st.session_state:
    st.session_state.summary = ""

# Adding Multiple Course Functionality
st.sidebar.title("Courses")
course_name = st.sidebar.text_input("Enter course name", value="General")

# Save New Course Data
if st.sidebar.button("Save Course"):
    saved, filename = save_course_history(course_name)
    if saved:
        st.sidebar.info(f"Course data saved to {filename}")
    else:
        st.sidebar.warning("No data to save for this course.")
if st.sidebar.button("Clear Current Session"):
    st.session_state.summary = ""
    st.session_state.messages = []
    st.rerun()

st.sidebar.markdown("---")

existing_files = [f for f in os.listdir(".") if f.endswith("_history.json")]

if existing_files:
    st.sidebar.subheader("Load or Delete Course")
    selected_file = st.sidebar.selectbox(
        "Select a course", ["--Select--"] + existing_files
    )

    # Create two columns for the buttons to sit side-by-side
    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("📂 Load"):
            if selected_file != "--Select--":
                with open(selected_file, "r", encoding="utf-8") as f:
                    course_data = json.load(f)
                    st.session_state.summary = course_data.get("summary", "")
                    st.session_state.messages = course_data.get("messages", [])

                    new_chat_history = []
                    for msg in st.session_state.messages:
                        role = "user" if msg["role"] == "user" else "model"
                        new_chat_history.append(
                            {"role": role, "parts": [{"text": msg["content"]}]}
                        )
                    st.session_state.chat_session = (
                        st.session_state.genai_client.chats.create(
                            model="gemini-2.5-flash", history=new_chat_history
                        )
                    )
                    st.rerun()

    with col2:
        if st.button("🗑️ Delete"):
            if selected_file != "--Select--":
                # Delete the physical file
                os.remove(selected_file)

                # If the deleted file was the one currently on screen, clear the screen
                # We check if the course name matches the filename (roughly)
                st.session_state.summary = ""
                st.session_state.messages = []

                st.sidebar.success(f"Deleted {selected_file}")
                time.sleep(1)  # Give the user a second to see the success message
                st.rerun()
            else:
                st.sidebar.warning("Select a course first.")


if st.session_state.summary:
    with st.expander("View Summary", expanded=True):
        st.subheader("Summary:")
        st.write(st.session_state.summary)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st._bottom:
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        if st.button("Quick Save"):
            save_course_history(course_name)
    with col2:
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()
    # Get text input from user and send to Gemini API, then display response
    if prompt := st.chat_input("Ask question here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.spinner("Generating response..."):
            response = st.session_state.chat_session.send_message(prompt)
            st.session_state.messages.append(
                {"role": "assistant", "content": response.text}
            )
            with st.chat_message("assistant"):
                st.markdown(response.text)


# Read PDF file
uploaded_files = st.file_uploader(
    "Upload a PDF file", type="pdf", accept_multiple_files=True
)

if uploaded_files and st.button("Summarize"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    text = ""
    for file in uploaded_files:
        status_text.text(f"Processing {file.name}...")
        progress_bar.progress((uploaded_files.index(file) + 1) / len(uploaded_files))
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() + "\n"

    with st.spinner("Generating summary..."):
        # Generate Summary using Gemini API
        response = st.session_state.chat_session.send_message(text + PROMPT)
        st.session_state.summary = response.text
        print(response.text)

    # Save to history.json
with open("history.json", "w", encoding="utf-8") as f:
    serializable = []

    # Use the session_state messages list instead of the Chat object
    # to avoid the 'no attribute history' error
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "model"
        serializable.append({"role": role, "parts": [{"text": msg["content"]}]})

    json.dump(serializable, f, ensure_ascii=False, indent=4)


# Print all available models and their descriptions, and save to a text file
# print("Available Gemini Models:")
# for model in client.models.list():
#     name = model.name if model.name else "Unnamed Model"
#     desc = model.description if model.description else "No description available."
#     print(name)
#     print(desc)
#     print("-" * 40)
#     with open("models.txt", "a", encoding="utf-8") as f:
#         f.write(name + "\n")
#         f.write(desc + "\n")
#         f.write("-" * 40 + "\n")
