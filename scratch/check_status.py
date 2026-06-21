import sqlite3
import os

db_path = 'database/manga_recap.db'
if not os.path.exists(db_path):
    print("Database not found.")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Buscar el manga
cursor.execute("SELECT id, titulo FROM mangas WHERE titulo LIKE '%Max%Level%Player%'")
mangas = cursor.fetchall()

if not mangas:
    print("Manga not found.")
else:
    for m_id, title in mangas:
        print(f"\nMANGA: {title} (ID: {m_id})")
        
# 2. Revisar capítulos
        cursor.execute("SELECT id, titulo FROM capitulos WHERE manga_id = ?", (m_id,))
        db_caps = cursor.fetchall()
        print(f"Capítulos registrados en DB: {len(db_caps)}")
        
        # 3. Contar guiones directamente
        cursor.execute("SELECT COUNT(*) FROM guiones WHERE chapter_id IN (SELECT id FROM capitulos WHERE manga_id = ?)", (m_id,))
        count = cursor.fetchone()[0]
        print(f"Guiones registrados en DB: {count}")

# 4. Revisar metadatos (en el sistema de archivos)
print("\n--- REVISANDO METADATOS EN DISCO ---")
outputs_dir = 'outputs'
for m_id, title in mangas:
    m_folder = title.replace(" ", "_").replace("'", "_").replace("-", "_") # Aproximación de nombre de carpeta
    # Buscar carpetas en outputs
    possible_folders = [d for d in os.listdir(outputs_dir) if d.lower() in title.lower().replace(" ", "_")]
    
    # En realidad el nombre suele ser el que devuelve el buscador sanitizado.
    # Vamos a probar con el nombre exacto de la carpeta que vimos antes:
    m_folder_fixed = "The_Max-Level_Player_s_100th_Regression"
    
    scripts_dir = os.path.join(outputs_dir, m_folder_fixed, "Scripts")
    if os.path.exists(scripts_dir):
        files = os.listdir(scripts_dir)
        print(f"Archivos en {scripts_dir}: {files}")
        metadata_files = [f for f in files if 'metadata' in f.lower() or 'youtube_data' in f.lower()]
        print(f"Metadatos encontrados: {metadata_files}")
    else:
        print(f"Carpeta de scripts no encontrada para {title}")

conn.close()
