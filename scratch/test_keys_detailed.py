import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

keys = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3")
]

models = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]

for idx, key in enumerate(keys, 1):
    print(f"\n==========================================")
    print(f"Testing GEMINI_API_KEY_{idx} (...{key[-4:] if key else 'None'}):")
    if not key:
        print("Key not found in .env")
        continue
    
    genai.configure(api_key=key)
    for model_name in models:
        try:
            print(f"  Trying model: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Say hello")
            print(f"  [SUCCESS] {model_name}: {response.text.strip()}")
        except Exception as e:
            print(f"  [FAILED] {model_name} failed with: {type(e).__name__}: {e}")
