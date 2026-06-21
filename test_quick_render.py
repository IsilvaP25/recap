import os
import asyncio
import fitz
from modules.pipeline import video_assembler, audio_generator, script_translator

async def render_partial(manga_folder, chapter_num):
    base_path = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(base_path, "pdf_storage", manga_folder, f"Capitulo_{chapter_num}.pdf")
    
    if not os.path.exists(pdf_path):
        print(f"[!] No se encontró el PDF: {pdf_path}")
        return

    # 1. Calcular el 25% de las páginas
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    limit = max(1, total_pages // 4)
    doc.close()

    print(f"\n>>> PROCESANDO: {manga_folder} (Cap {chapter_num})")
    
    # 2. Fase de Traducción (Si no existe el guion en español, traduce el existente en inglés)
    script_dir = os.path.join(base_path, "outputs", manga_folder, "Scripts")
    esp_script_path = os.path.join(script_dir, f"Capitulo_{chapter_num}_guion_ESP.txt")
    raw_script_path = os.path.join(script_dir, f"Capitulo_{chapter_num}_guion_raw.txt")

    if not os.path.exists(esp_script_path) and os.path.exists(raw_script_path):
        print(">>> No se encontró guion en español. Traducción en curso del guion inglés...")
        script_translator.translate_chapter(manga_folder, chapter_num)
    
    # 3. Fase de Audio
    print(f">>> Generando audio para las primeras {limit} páginas...")
    audio_out_dir = os.path.join(base_path, "outputs", manga_folder, "_TEMP", f"Capitulo_{chapter_num}", "audio")
    
    if os.path.exists(esp_script_path) or os.path.exists(raw_script_path):
        # Preferir ESP
        final_script = esp_script_path if os.path.exists(esp_script_path) else raw_script_path
        data = audio_generator.parse_script(final_script)
        # Limitar datos al 25%
        limited_data = {k: v for k, v in data.items() if k <= limit}
        await audio_generator.generate_audio_for_pages(limited_data, audio_out_dir)
    else:
        print(f"[!] No se encontró ningún guion para audio.")

    # 4. Fase de Video
    print(f">>> Renderizando video (25%)...")
    video_assembler.assemble_video(
        manga_name=manga_folder,
        chapter_num=chapter_num,
        pdf_path=pdf_path,
        mode="full",
        page_limit=limit
    )

    # 5. Mover el resultado a la raíz
    final_video_path = os.path.join(base_path, "outputs", manga_folder, "VIDEOS", f"Capitulo_{chapter_num}.mp4")
    if os.path.exists(final_video_path):
        test_name = f"test_{manga_folder.split('_')[0]}_{manga_folder.split('_')[1]}.mp4"
        root_dest = os.path.join(base_path, test_name)
        import shutil
        if os.path.exists(root_dest): os.remove(root_dest)
        shutil.move(final_video_path, root_dest)
        print(f"\n[OK] PRUEBA LISTA EN: {root_dest}")

async def main():
    mangas = [
        "The_Max-Level_Player_s_100th_Regression",
        "The_Death_Mage_Who_Doesn_t_Want_a_Fourth_Time"
    ]
    for manga in mangas:
        try:
            await render_partial(manga, 3)
        except Exception as e:
            print(f"[ERROR] Falló {manga}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
