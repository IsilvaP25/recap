import os
import sys
import sqlite3
import argparse

# Asegurar importación de módulos del proyecto
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.append(base_dir)

from modules import db_manager, api_config
from modules.gemini import vector_manager
from google import genai

def list_mangas_with_scripts():
    """Retorna una lista de mangas que tienen al menos un guion en la base de datos."""
    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT manga FROM scripts ORDER BY manga")
    mangas = [row[0] for row in cursor.fetchall()]
    conn.close()
    return mangas

def get_chapters_for_manga(manga_name):
    """Retorna los capítulos ordenados ascendentemente para un manga específico."""
    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT chapter FROM scripts WHERE manga = ? ORDER BY chapter ASC",
        (manga_name,)
    )
    chapters = [row[0] for row in cursor.fetchall()]
    conn.close()
    return chapters

def get_chapter_script_text(manga_name, chapter_num):
    """Concatena el texto de todas las páginas de un capítulo."""
    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT content FROM scripts WHERE manga = ? AND chapter = ? ORDER BY page_num ASC",
        (manga_name, chapter_num)
    )
    rows = cursor.fetchall()
    conn.close()
    return "\n".join([r[0] for r in rows])

def backfill_manga_memory(manga_name, force=False):
    manga_key = manga_name.replace(' ', '_')
    print(f"\n==================================================")
    print(f"PROCESANDO MEMORIA HISTÓRICA PARA: {manga_name.replace('_', ' ')}")
    print(f"==================================================")
    
    chapters = get_chapters_for_manga(manga_name)
    if not chapters:
        print(f"  [AVISO] No se encontraron guiones en la BD para {manga_name}.")
        return
        
    print(f"  Detectados {len(chapters)} capítulos en la base de datos.")
    
    collection = vector_manager.get_collection()
    client = api_config.obtener_cliente_gemini()
    
    current_history = ""
    
    # Intentar obtener el último historial guardado en SQLite por si empezamos a mitad
    db_hist, _, _ = db_manager.get_story_history(manga_name)
    if db_hist:
        current_history = db_hist
        
    for chapter in chapters:
        doc_id = f"{manga_key}_cap_{chapter}"
        
        # 1. Comprobar si ya existe en ChromaDB
        exists_in_vector = False
        if not force:
            try:
                res = collection.get(ids=[doc_id])
                if res and res.get("documents") and len(res["documents"]) > 0:
                    exists_in_vector = True
                    # Actualizar nuestra variable de historia actual con el documento de ChromaDB
                    current_history = res["documents"][0]
                    print(f"  [OMITIR] Capítulo {chapter} ya indexado en base vectorial. Cargando historial previo...")
            except Exception as e:
                print(f"  [AVISO] Error al verificar ChromaDB para Cap {chapter}: {e}")
                
        if exists_in_vector:
            continue
            
        # 2. Obtener el texto completo del capítulo
        chapter_text = get_chapter_script_text(manga_name, chapter)
        if not chapter_text:
            print(f"  [ERROR] No se pudo leer el guion del Capítulo {chapter}. Saltando...")
            continue
            
        print(f"  [PROCESANDO] Generando memoria para Capítulo {chapter}...")
        
        # 3. Generar el resumen ejecutivo usando Gemini 2.5 Flash-Lite
        prompt = f"""
        Current Story History: {current_history if current_history else "No history yet."}
        
        New Chapter ({chapter}) Script:
        {chapter_text[:6000]}...
        
        Update the story history. Provide a 5-line executive summary of the story events SO FAR in Spanish.
        Focus only on the plot facts and character evolution. Output ONLY the summary.
        """
        
        intentos_ia = 0
        summary = None
        while intentos_ia < 5:
            try:
                # Llamar a Gemini usando el nuevo SDK de api_config
                response = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=prompt
                )
                summary = response.text.strip()
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    print(f"  [AVISO] Cuota agotada en gemini-2.5-flash-lite. Rotando llaves (Intento {intentos_ia + 1}/5)...")
                    try:
                        from modules import api_rotator
                        keys_list = api_config.obtener_api_keys_disponibles()
                        curr_idx = api_config.get_current_key_index()
                        if curr_idx < len(keys_list):
                            api_rotator.report_failed_key(keys_list[curr_idx])
                    except Exception:
                        pass
                    from modules import token_monitor
                    if token_monitor.validar_acceso_gemini():
                        client = api_config.obtener_cliente_gemini()
                        intentos_ia += 1
                        import time
                        time.sleep(1)
                        continue
                    else:
                        print("  [ERROR] No hay más API keys disponibles en el pool.")
                        break
                else:
                    print(f"  [ERROR] Fallo en la llamada a Gemini: {e}")
                    break
                    
        if not summary:
            print(f"  [ERROR] No se pudo generar el resumen del Capítulo {chapter}. Deteniendo manga...")
            break
            
        try:
            # Guardar en SQLite (Base de datos relacional)
            db_manager.save_story_history(manga_name, chapter, summary)
            
            # Guardar en ChromaDB (Base de datos vectorial)
            vector_manager.guardar_resumen_capitulo(manga_name, chapter, summary)
            
            # Actualizar historia para el siguiente capítulo
            current_history = summary
        except Exception as e:
            print(f"  [ERROR] Error al guardar en base de datos para Capítulo {chapter}: {e}")
            break
            
    print(f"[OK] Finalizado procesamiento de {manga_name}.")

def main():
    parser = argparse.ArgumentParser(description="Backfill para base de datos vectorial ChromaDB (Mangas largos)")
    parser.add_argument("--manga", help="Nombre del manga específico para procesar")
    parser.add_argument("--force", action="store_true", help="Forzar la regeneración de resúmenes e indexación")
    args = parser.parse_args()
    
    db_manager.init_db()
    
    # Verificar si el proveedor es Gemini
    if api_config.obtener_ia_provider() != "gemini":
        print("[ERROR] Este script solo es compatible con el proveedor 'gemini'.")
        sys.exit(1)
        
    mangas_disponibles = list_mangas_with_scripts()
    if not mangas_disponibles:
        print("[ERROR] No se encontraron mangas con guiones en la base de datos relacional.")
        sys.exit(1)
        
    if args.manga:
        # Procesar manga específico
        manga_target = args.manga.replace(' ', '_')
        if manga_target not in mangas_disponibles:
            print(f"[ERROR] El manga '{args.manga}' no tiene guiones en la base de datos.")
            print(f"Mangas disponibles: {mangas_disponibles}")
            sys.exit(1)
        backfill_manga_memory(manga_target, force=args.force)
    else:
        # Menú interactivo
        print("\n=== MOTOR DE SINCRONIZACIÓN VECTORIAL ===")
        print("1. Procesar TODOS los mangas pendientes")
        print("2. Procesar un manga específico")
        print("3. Salir")
        
        opt = input("\nSelecciona una opción: ")
        if opt == "1":
            confirm = input("\n¿Estás seguro de procesar todos los mangas? Esto consumirá tokens de la API. (s/n): ").lower()
            if confirm == "s":
                for m in mangas_disponibles:
                    backfill_manga_memory(m, force=args.force)
        elif opt == "2":
            print("\nMangas disponibles:")
            for idx, m in enumerate(mangas_disponibles, 1):
                print(f"{idx}. {m.replace('_', ' ')}")
            sel = input("\nSelecciona el número de manga: ")
            try:
                m_idx = int(sel) - 1
                if 0 <= m_idx < len(mangas_disponibles):
                    backfill_manga_memory(mangas_disponibles[m_idx], force=args.force)
                else:
                    print("Número fuera de rango.")
            except ValueError:
                print("Entrada no válida.")
        else:
            print("Saliendo...")

if __name__ == "__main__":
    main()
