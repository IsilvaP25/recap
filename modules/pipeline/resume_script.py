import os
import re
import google.generativeai as genai
from dotenv import load_dotenv
import fitz
from PIL import Image
import io
import time

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Use a different model to bypass the specific 3.0 flash quota
MODEL_NAME = 'gemini-2.0-flash'

def get_lore_context():
    try:
        with open("lore_bible.json", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "{}"

def clean_garbage_text(text):
    garbage_patterns = [
        r'^(?:This is the\s+)?cover\s*(?:page)?[:\-\s]*',
        r'^(?:On this\s+)?page[:\-\s]*\d*',
        r'^(?:Image of\s+)?cover[:\-\s]*',
        r'^Transcription[:\-\s]*',
        r'^Script[:\-\s]*'
    ]
    for pattern in garbage_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE).strip()
    return text

def get_system_instruction():
    lore = get_lore_context()
    return f"""
Senior Scriptwriter. Lore (Spanish): {lore}.
ABSOLUTE RULE: Output ONLY the story narration and markers (### PAGE_XX).
ZERO TOLERANCE: Do NOT mention "Cover", "Page", or "Image". START DIRECTLY with the action.
Example:
### PAGE_01
(Story Text)
"""

def resume_script(pdf_path, output_file, start_page):
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=get_system_instruction())
    doc = fitz.open(pdf_path)
    
    with open(output_file, "a", encoding="utf-8") as f:
        for i in range(start_page - 1, len(doc)):
            page_num = i + 1
            print(f"Resumiendo: Generando para P‡gina {page_num}...")
            try:
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                
                response = model.generate_content([f"Generate EXCLUSIVELY the story narration for page {page_num}. No technical or visual descriptions.", img])
                clean_txt = clean_garbage_text(response.text)
                f.write(f"\n\n{clean_txt}")
                time.sleep(2)
            except Exception as e:
                print(f"Error en p‡gina {page_num}: {e}")
                
    doc.close()

if __name__ == "__main__":
    manga_path = "PDFs/I_Got_A_New_Skill_Every_Time_I_Was_Exiled__And_After_100_Different_Worlds__I_Was_Unmatched/Capitulo_1.pdf"
    resume_script(manga_path, "Capitulo_1_Guion.txt", 23)
