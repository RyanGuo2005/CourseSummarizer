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
from supabase import create_client

# ==============================================================
# CONSTANTS / METHODS
# ==============================================================
PROMPT = """
Please summarize this pdf lesson into concise bullet points, highlighting the key concepts and important details. 
The summary should be clear and easy to understand, suitable for quick review and study.
If possible, split up by lesson sections, and include any important formulas, definitions, or examples mentioned in the text.
Mention how to solve any problems or exercises included in the lesson, and provide step-by-step explanations if applicable.
"""
TABLE_NAME = "Courses"


def save_to_db(name, summary, messages):
    data = {
        "course_name": name,
        "summary": summary,
        "messages": json.dumps(messages),  # Convert list to JSON string
        "date": str(date.today()),
    }
    response = (
        supabase.table(TABLE_NAME).upsert(data, on_conflict="course_name").execute()
    )
    return True if response.data else False


def retrieve_all_courses():
    response = supabase.table(TABLE_NAME).select("course_name").execute()
    if response.data:
        return list(
            set(item["course_name"] for item in response.data)
        )  # Return unique course names
    else:
        # st.sidebar.error("Failed to retrieve courses from database.")
        return []


def retrieve_course_data(course_name):
    response = (
        supabase.table(TABLE_NAME)
        .select("*")
        .eq("course_name", course_name)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if response.data:
        return response.data[
            0
        ]  # Assuming course names are unique, return the first match
    else:
        return None


def delete_course_data(course_name):
    response = (
        supabase.table(TABLE_NAME).delete().eq("course_name", course_name).execute()
    )
    if response.data:
        st.sidebar.success(
            f"Course '{course_name}' deleted from database successfully!"
        )
        time.sleep(1)
    else:
        st.sidebar.error(f"Failed to delete course '{course_name}' from database.")
        time.sleep(1)
    return response


# ==============================================================
# Retrieve API key and initialize client
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

# Initialize database
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

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
        model="gemini-flash-latest", history=chat_history
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
    saved = save_to_db(course_name, st.session_state.summary, st.session_state.messages)
    if saved:
        st.sidebar.info(f"Course data saved to database for '{course_name}'")
    else:
        st.sidebar.warning("Failed to save course data to database.")
if st.sidebar.button("Clear Current Session"):
    st.session_state.summary = ""
    st.session_state.messages = []
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Load or Delete Course")

db_courses = retrieve_all_courses()

if db_courses:
    selected_course = st.sidebar.selectbox(
        "Select a course to load", ["--Select--"] + db_courses
    )

    # Create two columns for the buttons to sit side-by-side
    col1, col2 = st.sidebar.columns(2)

    with col1:
        if selected_course != "--Select--" and st.button(
            "Load Course", use_container_width=True
        ):
            course_data = retrieve_course_data(selected_course)
            if course_data:
                # Retrieve Summary and Messages from database
                st.session_state.summary = course_data.get("summary", "")

                # Convert messages to usable format
                raw_messages = course_data.get("messages", [])
                st.session_state.messages = (
                    json.loads(raw_messages)
                    if isinstance(raw_messages, str)
                    else raw_messages
                )

                # Resync the API chat session with the loaded messages
                new_chat_history = []
                for msg in st.session_state.messages:
                    role = "user" if msg["role"] == "user" else "model"
                    new_chat_history.append(
                        {"role": role, "parts": [{"text": msg["content"]}]}
                    )

                st.session_state.chat_session = (
                    st.session_state.genai_client.chats.create(
                        model="gemini-flash-latest", history=new_chat_history
                    )
                )
                st.rerun()

    with col2:
        if selected_course != "--Select--" and st.button(
            "Delete Course", use_container_width=True
        ):
            delete_course_data(selected_course)
            st.session_state.summary = ""
            st.session_state.messages = []
            st.rerun()
else:
    st.sidebar.info(
        "No courses found in database. Please save a course to see it here."
    )

if st.session_state.summary:
    with st.expander("View Summary", expanded=True):
        st.subheader("Summary:")
        st.markdown(st.session_state.summary)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st._bottom:
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        if st.button("Quick Save"):
            save_to_db(course_name, st.session_state.summary, st.session_state.messages)
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
    status_text = st.empty()

    with st.spinner("Generating summary..."):
        # Generate Summary using Gemini API
        response = st.session_state.chat_session.send_message(text + PROMPT)
        st.session_state.summary = response.text
        st.rerun()
        print(response.text)

# Print all available models and their descriptions, and save to a text file
# print("Available Gemini Models:")
# API_KEY = os.getenv("GEMINI_API_KEY")
# client = genai.Client(api_key=API_KEY)
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
