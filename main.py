from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from fpdf import FPDF
from pypdf import PdfReader
from datetime import date
import re

# ==============================================================
# CONSTANTS
# ==============================================================
PROMPT = """
oh my god i'm blooming
"""
# ==============================================================
# Retrieve API key and initialize client
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

client = genai.Client(api_key=API_KEY)

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

# Generate content using the Gemini API
try:
    response = client.models.generate_content(model="gemini-2.5-flash", contents=PROMPT)
    print(response.text)
except Exception as e:
    print(f"An error occurred: {e}")
