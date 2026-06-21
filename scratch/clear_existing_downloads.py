import os
import shutil
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Database paths
db_recap_path = os.path.join(BASE_DIR, 'database', 'manga_recap.db')
db_pipeline_path = os.path.join(BASE_DIR, 'database', 'manga_pipeline.db')

def clear_directory(path):
    if not os.path.exists(path):
        return
    print(f"Limpiando directorio: {path}")
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        try:
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
        except Exception as e:
            print(f"Error borrando {item_path}: {e}")

def reset_recap_db():
    print(f"Reiniciando DB: {db_recap_path}")
    if os.path.exists(db_recap_path):
        try:
            os.remove(db_recap_path)
            print("DB manga_recap.db eliminada.")
        except Exception as e:
            print(f"Error eliminando DB: {e}")
    # We will let the app recreate it on startup via database.inicializar_db()

def reset_pipeline_db():
    print(f"Reiniciando DB: {db_pipeline_path}")
    if os.path.exists(db_pipeline_path):
        try:
            os.remove(db_pipeline_path)
            print("DB manga_pipeline.db eliminada.")
        except Exception as e:
            print(f"Error eliminando DB: {e}")

if __name__ == "__main__":
    raw_downloads_path = os.path.join(BASE_DIR, 'raw_downloads')
    pdf_storage_path = os.path.join(BASE_DIR, 'pdf_storage')
    outputs_path = os.path.join(BASE_DIR, 'outputs')
    
    clear_directory(raw_downloads_path)
    clear_directory(pdf_storage_path)
    clear_directory(outputs_path)
    
    reset_recap_db()
    reset_pipeline_db()
    
    # Re-init databases
    import sys
    sys.path.append(BASE_DIR)
    from modules import database
    from modules.pipeline import db_manager
    
    database.inicializar_db()
    db_manager.init_db()
    print("Bases de datos reiniciadas e inicializadas con éxito.")
    print("¡Limpieza completada!")
