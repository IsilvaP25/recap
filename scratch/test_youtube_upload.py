import os
import sys
import datetime
import shutil

# Asegurar import de modulos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from modules.pipeline import db_manager
from modules.flows import shorts_flow

# Importar uploader del sibling api
parent_dir = os.path.dirname(BASE_DIR)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
from api import youtube_uploader

def test_scheduling_and_upload():
    print("=== INICIANDO PRUEBA DE SUBIDA Y PROGRAMACION ===")
    
    # Forzar modo MOCK para las pruebas unitarias
    os.environ["MOCK_YOUTUBE"] = "true"
    youtube_uploader.MOCK_YOUTUBE = True
    
    # 1. Inicializar DB
    db_manager.init_db()
    
    # Resetear tabla shorts para la prueba
    import sqlite3
    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM shorts")
    conn.commit()
    conn.close()
    print("[1] Base de datos de prueba limpia.")

    # 2. Caso A: No hay shorts previos subidos
    # El primer short debe programarse para hoy o mañana a las 10:00 AM
    print("\n[2] Probando cálculo de fecha para primer Short (sin historial)...")
    fecha_1 = shorts_flow.calcular_fecha_10am(None)
    print(f"Fecha calculada para primer video: {fecha_1}")
    
    # Validar que contenga la hora 10:00:00
    time_str = "10:00:00"
    assert time_str in fecha_1, f"Error: La hora esperada {time_str} no está en la fecha calculada {fecha_1}"
    print("[OK] Primer fecha calculada correctamente.")

    # 3. Caso B: Insertar un short con fecha e incrementarlo secuencialmente (Calendario de 1 short diario a las 10:00 AM)
    print("\n[3] Probando incremento consecutivo de fecha (D+1)...")
    last_date_str = "2026-05-25T15:00:00-04:00" # Simula el fin de la subida 2 anterior (a las 3:00 PM)
    
    # Marcamos un manga de prueba como subido en esa fecha (is_uploaded = 2)
    db_manager.save_short_script("manga_prueba_1", "Contenido 1")
    db_manager.mark_short_as_uploaded_with_date_step2("manga_prueba_1", "yt_id_1", last_date_str)
    
    # Obtenemos la última fecha de la DB
    db_last_date = db_manager.get_last_scheduled_short_date()
    print(f"Última fecha obtenida de la base de datos: {db_last_date}")
    assert db_last_date == last_date_str, f"Error obteniendo fecha de la DB: {db_last_date} != {last_date_str}"
    
    # Calculamos la siguiente (debería ser el día siguiente a las 10:00 AM)
    fecha_2 = shorts_flow.calcular_fecha_10am(db_last_date)
    print(f"Siguiente fecha calculada: {fecha_2}")
    
    # Debe ser el 2026-05-26 a las 10:00
    assert "2026-05-26T10:00:00" in fecha_2, f"Error: Se esperaba 2026-05-26T10:00:00 en {fecha_2}"
    print("[OK] Incremento de fecha diario calculado correctamente.")

    # 4. Caso C: Simulación de subida doble y procesamiento con Mock
    print("\n[4] Probando simulación de subida doble (Mock) y borrado de archivo local...")
    
    # Crear archivo local ficticio
    dummy_video_path = os.path.join(BASE_DIR, "outputs", "manga_prueba_2", "VIDEOS")
    os.makedirs(dummy_video_path, exist_ok=True)
    dummy_file = os.path.join(dummy_video_path, "Short_1.mp4")
    
    with open(dummy_file, "w") as f:
        f.write("mock video content")
        
    print(f"Creado archivo dummy de video en: {dummy_file}")
    assert os.path.exists(dummy_file), "No se pudo crear el archivo dummy de video."

    # Metadatos dummy
    dummy_metadata_path = os.path.join(BASE_DIR, "outputs", "manga_prueba_2", "Scripts")
    os.makedirs(dummy_metadata_path, exist_ok=True)
    dummy_meta_file = os.path.join(dummy_metadata_path, "short_youtube_data.json")
    with open(dummy_meta_file, "w") as f:
        f.write('{"clickbait_title": "Manga Prueba 2", "description": "Desc", "tags": []}')
        
    # Registrar script e indicar que video local está creado
    db_manager.save_short_script("manga_prueba_2", "Contenido 2")
    db_manager.mark_short_video_created("manga_prueba_2", 1)
    
    # Ejecutar procesar_subida_manga (Mock)
    uploader_path = os.path.join(parent_dir, "api", "youtube_uploader.py")
    success = shorts_flow.procesar_subida_manga("manga_prueba_2", BASE_DIR, uploader_path, True, None)
    
    assert success is True, "procesar_subida_manga falló"
    
    # Verificar que el archivo local fue borrado
    assert not os.path.exists(dummy_file), "Error: El archivo de video local no fue eliminado."
    
    # Verificar que en la DB quedó marcado como is_uploaded = 2
    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT is_uploaded, youtube_id FROM shorts WHERE manga = 'manga_prueba_2'")
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None, "No se encontró el registro en la base de datos"
    assert row[0] == 2, f"Se esperaba is_uploaded = 2, se obtuvo {row[0]}"
    assert "," in row[1], f"Se esperaban dos IDs concatenados en youtube_id, se obtuvo {row[1]}"
    
    print("[OK] Simulación de subida doble y borrado de archivo completados correctamente.")
    
    # Limpiar carpeta outputs de prueba
    try:
        shutil.rmtree(os.path.join(BASE_DIR, "outputs", "manga_prueba_1"))
        shutil.rmtree(os.path.join(BASE_DIR, "outputs", "manga_prueba_2"))
    except Exception:
        pass
        
    print("\n=== TODAS LAS PRUEBAS PASARON CON EXITO ===")

if __name__ == "__main__":
    test_scheduling_and_upload()
