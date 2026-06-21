import sys
import os
import time
import threading
from unittest.mock import MagicMock

# Añadir la carpeta raíz al path para importar app
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

# Mockear el downloader_flow antes de importar app para evitar llamadas de red/base de datos reales
import modules.flows.downloader_flow as downloader_flow

# Guardamos la función original por si acaso
original_ejecutar = downloader_flow.ejecutar_descarga_manga

execution_order = []
execution_lock = threading.Lock()

def mocked_ejecutar_descarga_manga(m_id, m_titulo, automatico=False, forzar=False, manga_data=None):
    with execution_lock:
        execution_order.append(f"START_{m_titulo}")
    print(f"\n[MOCK] Iniciando descarga simulada de: {m_titulo}...")
    time.sleep(1.5)  # Simular tiempo de descarga
    with execution_lock:
        execution_order.append(f"END_{m_titulo}")
    print(f"[MOCK] Finalizada descarga simulada de: {m_titulo}")

downloader_flow.ejecutar_descarga_manga = mocked_ejecutar_descarga_manga

# Importar app después del mock
from app import app, _download_queue

def test_sequential_queue():
    client = app.test_client()

    print("\n--- PASO 1: Enviando descargas simultáneas a la cola ---")
    
    # Mandar manga A
    resp_a = client.post('/api/download_manga', json={
        "manga_id": "manga_a_id",
        "manga_title": "Manga A",
        "manga_data": {}
    })
    print(f"Respuesta Manga A: {resp_a.get_json()}")

    # Mandar manga B inmediatamente después
    resp_b = client.post('/api/download_manga', json={
        "manga_id": "manga_b_id",
        "manga_title": "Manga B",
        "manga_data": {}
    })
    print(f"Respuesta Manga B: {resp_b.get_json()}")

    print("\n--- PASO 2: Verificando estado de la cola inmediatamente ---")
    time.sleep(0.1)  # Pequeño delay para dejar que el worker empiece
    
    resp_status = client.get('/api/download_queue/status')
    status_data = resp_status.get_json()
    print(f"Estado de la cola (inicial): {status_data}")
    
    # Debería estar descargando Manga A, con Manga B en cola o ya procesando
    assert status_data["current"] == "Manga A", f"Se esperaba 'Manga A' pero se obtuvo {status_data['current']}"
    
    print("\n--- PASO 3: Esperando que termine Manga A y comience Manga B ---")
    time.sleep(1.6)  # Esperar suficiente para que Manga A termine (toma 1.5s)
    
    resp_status = client.get('/api/download_queue/status')
    status_data = resp_status.get_json()
    print(f"Estado de la cola (mitad): {status_data}")
    
    # Debería estar descargando Manga B ahora
    assert status_data["current"] == "Manga B", f"Se esperaba 'Manga B' pero se obtuvo {status_data['current']}"

    print("\n--- PASO 4: Esperando que terminen todas las descargas ---")
    time.sleep(1.6)  # Esperar que Manga B termine (toma 1.5s)
    
    resp_status = client.get('/api/download_queue/status')
    status_data = resp_status.get_json()
    print(f"Estado de la cola (final): {status_data}")
    
    # Debería estar vacío
    assert status_data["current"] is None, f"Se esperaba None pero se obtuvo {status_data['current']}"
    assert status_data["queue_size"] == 0, f"Se esperaba tamaño 0 pero se obtuvo {status_data['queue_size']}"

    print("\n--- PASO 5: Verificando el orden estricto de ejecución secuencial ---")
    print(f"Orden de ejecución registrado: {execution_order}")
    
    expected_order = ["START_Manga A", "END_Manga A", "START_Manga B", "END_Manga B"]
    assert execution_order == expected_order, f"Incorrect order! Expected {expected_order} but got {execution_order}"
    print("\n[SUCCESS] PRUEBA EXITOSA! La cola de descarga proceso los mangas en orden secuencial estricto y el endpoint de estado respondio correctamente.")

if __name__ == "__main__":
    test_sequential_queue()
