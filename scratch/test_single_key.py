import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

keys = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3")
]

for idx, key in enumerate(keys, 1):
    print(f"\nTesting GEMINI_API_KEY_{idx} (...{key[-4:] if key else 'None'}):")
    if not key:
        print("Key not found in .env")
        continue
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content("Say hello")
        print(f"Success! Response: {response.text.strip()}")
    except Exception as e:
        print(f"Failed with exception: {type(e).__name__}: {e}")
