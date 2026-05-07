import os
from dotenv import load_dotenv

load_dotenv()
load_dotenv("api.env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
