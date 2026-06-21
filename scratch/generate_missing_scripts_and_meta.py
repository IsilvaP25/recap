import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_BASE = os.path.join(BASE_DIR, "pdf_storage")
SCRIPTS_DIR = os.path.join(BASE_DIR, "modules", "pipeline")

# Add paths to pythonpath
env = os.environ.copy()
env["PYTHONPATH"] = BASE_DIR + os.pathsep + SCRIPTS_DIR + os.pathsep + env.get("PYTHONPATH", "")

def run_step(step_name, args):
    print(f"\n>>> Running: {step_name}")
    cmd = [sys.executable] + args
    try:
        res = subprocess.run(cmd, check=True, env=env, cwd=BASE_DIR)
        print(f"[{step_name}] Success!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[{step_name}] Failed with return code {e.returncode}")
        return False

def generate_for_manga(manga):
    meta_json = os.path.join(BASE_DIR, "outputs", manga, "Scripts", "short_youtube_data.json")
    if os.path.exists(meta_json):
        print(f"\n[SKIP] {manga} already has short_youtube_data.json. Skipping all generation steps.")
        return True

    pdf_dir = os.path.join(PDF_BASE, manga)
    if not os.path.exists(pdf_dir):
        print(f"Directory {pdf_dir} does not exist.")
        return False
        
    pdf_path = os.path.join(pdf_dir, "Capitulo_1.pdf")
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(pdf_dir, "1.pdf")
    if not os.path.exists(pdf_path):
        pdfs = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
        if pdfs:
            pdf_path = os.path.join(pdf_dir, sorted(pdfs)[0])
        else:
            pdf_path = None
            
    if not pdf_path:
        print(f"Could not find PDF in {pdf_dir}.")
        return False
        
    print(f"\n==================================================")
    print(f"Generating Short Script and Metadata for: {manga}")
    print(f"PDF Path: {pdf_path}")
    print(f"==================================================")
    
    # Step 1: Generate Short script (Gemini)
    script_script = os.path.join(SCRIPTS_DIR, "manga_scriptwriter.py")
    ok = run_step(f"Scriptwriter for {manga}", [script_script, "--manga", manga, "--chapter", "1", "--pdf", pdf_path, "--mode", "short"])
    if not ok:
        return False
        
    # Step 2: Translate script (English -> Spanish)
    translator_script = os.path.join(SCRIPTS_DIR, "script_translator.py")
    ok = run_step(f"Translator for {manga}", [translator_script, "--manga", manga, "--chapter", "1"])
    if not ok:
        return False
        
    # Step 3: Generate metadata (Gemini)
    meta_script = os.path.join(SCRIPTS_DIR, "metadata_generator.py")
    ok = run_step(f"Metadata Generator for {manga}", [meta_script, "--manga", manga, "--short"])
    return ok

def main():
    mangas_to_generate = [
        "A_Sword_Master_Childhood_Friend_Power_Harassed_Me_Harshly_So_I_Broke_Off_Our_Relationship_And_Make_A_Fresh_Start_At_The_Frontier_As_A_Magic_Swordsman",
        "Dear_Shimazaki_in_the_Peaceful_Land",
        "The_Exiled_Reincarnated_Heavy_Knight_Is_Unrivaled_in_Game_Knowledge",
        "The_Girl_Monster_I_Saved",
        "To_Aru_Majutsu_no_Kinsho_Mokuroku"
    ]
    
    success_count = 0
    for manga in mangas_to_generate:
        if generate_for_manga(manga):
            success_count += 1
            
    # Also generate metadata for Single_Dad_In_Another_World
    print(f"\n==================================================")
    print(f"Generating Short Metadata for: Single_Dad_In_Another_World")
    print(f"==================================================")
    meta_script = os.path.join(SCRIPTS_DIR, "metadata_generator.py")
    dad_ok = run_step("Metadata Generator for Single_Dad_In_Another_World", [meta_script, "--manga", "Single_Dad_In_Another_World", "--short"])
    
    print(f"\n=== FINISHED PROCESS ===")
    print(f"Manga scripts/metadata fully generated: {success_count}/{len(mangas_to_generate)}")
    print(f"Single_Dad_In_Another_World metadata generated: {'Yes' if dad_ok else 'No'}")

if __name__ == "__main__":
    main()
