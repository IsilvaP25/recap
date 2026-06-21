import os
import sys
import sqlite3

# Reconfigure stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_proj)

from modules import api_config, token_monitor

def generate_prompts():
    db_path = os.path.join(base_proj, "database", "manga_recap.db")
    manga_name = "A_Single_Aristocrat_Enjoys_a_Different_World_The_Graceful_Life_of_a_Man_Who_Never_Gets_Married"
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT resumen FROM mangas WHERE titulo LIKE ?", ("%Single_Aristocrat%",))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        print("Manga not found in database.")
        return
        
    summary = row[0]
    print("Manga Summary:", summary)
    
    if token_monitor.validar_acceso_gemini():
        client = api_config.obtener_cliente_gemini()
        modelo = api_config.nombre_modelo_ia()
    else:
        print("No valid Gemini API key found.")
        return

    parts = [
        ("Parte 1", "Capítulos 1 al 7", "introducción del aristócrata Zilkan y su nueva vida de soltero en el mundo diferente disfrutando de su comida y magia"),
        ("Parte 2", "Capítulos 8 al 17", "Zilkan se encuentra con un artesano mágico y explora nuevos artefactos y misterios de la ciudad"),
        ("Parte 3", "Capítulos 18 al 24", "Zilkan regresa triunfal a su hogar y muestra sus grandes habilidades y elegancia frente a otros nobles"),
        ("Parte 4", "Capítulos 25 al 31", "Zilkan continúa su vida pacífica de soltero, cocinando y decorando su hogar con nuevos objetos mágicos")
    ]
    
    for part_name, caps, context in parts:
        prompt_ia = (
            f"Actúa como un experto en miniaturas y CTR de YouTube.\n"
            f"Diseña un prompt altamente descriptivo en INGLÉS para un generador de imágenes de IA (como Imagen 3/4 o Flux) "
            f"para una miniatura basada en el manga:\n"
            f"Título: A Single Aristocrat Enjoys a Different World\n"
            f"Sinopsis: {summary}\n"
            f"Detalles de esta parte ({part_name} - {caps}): {context}\n\n"
            f"REGLAS DEL PROMPT A GENERAR:\n"
            f"1. Estilo visual: Anime vibrante, ilustración de alta calidad de estilo manga/anime moderno, colores cálidos e iluminación cinematográfica, 8k.\n"
            f"2. Composición: Muestra al protagonista Zilkan (un joven noble de cabello oscuro y anteojos, con vestimentas elegantes) en una pose atractiva y relajada, realizando actividades relacionadas con el contexto.\n"
            f"3. NO agregues textos dibujados en la imagen (este se superpondrá digitalmente después).\n"
            f"4. Devuelve ÚNICAMENTE el prompt de la imagen en inglés. Sin introducciones ni comentarios adicionales."
        )
        
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=prompt_ia
            )
            print(f"\n=========================================")
            print(f"PROMPT PARA {part_name} ({caps}):")
            print(f"=========================================")
            print(response.text.strip())
        except Exception as e:
            print(f"Error generating prompt for {part_name}: {e}")

if __name__ == "__main__":
    generate_prompts()
