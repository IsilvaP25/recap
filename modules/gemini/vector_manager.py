import os
import sys
import chromadb
from google import genai

# Asegurar importación de módulos del proyecto
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if base_dir not in sys.path:
    sys.path.append(base_dir)

from modules import api_config

VECTORS_DIR = os.path.join(base_dir, "database", "vectors")
COLLECTION_NAME = "long_videos_lore"

_chroma_client = None
_collection = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(VECTORS_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=VECTORS_DIR)
    return _chroma_client

def get_collection():
    global _collection
    if _collection is None:
        client = get_chroma_client()
        # Creamos o cargamos la colección. No le pasamos embedding_function por defecto
        # ya que calcularemos y enviaremos los embeddings manualmente usando Gemini.
        _collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return _collection

def generar_embedding(texto):
    """Genera el embedding de un texto de forma nativa usando Gemini gemini-embedding-2."""
    # Obtenemos el cliente con rotación de claves configurada en api_config
    client = api_config.obtener_cliente_gemini()
    
    intentos = 0
    while intentos < 3:
        try:
            response = client.models.embed_content(
                model="gemini-embedding-2",
                contents=texto
            )
            # Retorna el vector de floats
            return response.embeddings[0].values
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                print(f"  [VECTORS] [AVISO] Cuota de embeddings agotada. Rotando claves (Intento {intentos + 1}/3)...")
                # Forzar obtención de cliente con nueva clave rotada
                from modules import token_monitor
                if token_monitor.validar_acceso_gemini():
                    client = api_config.obtener_cliente_gemini()
                    intentos += 1
                    continue
                else:
                    print("  [VECTORS] [ERROR] No hay más API Keys con cuota disponible.")
                    raise e
            else:
                print(f"  [VECTORS] [ERROR] Error al generar embedding con Gemini: {e}")
                raise e
    raise RuntimeError("No se pudo generar el embedding tras 3 intentos.")

def guardar_resumen_capitulo(manga_name, chapter_num, resumen):
    """Guarda el resumen de un capítulo en la base de datos vectorial ChromaDB."""
    manga_key = manga_name.replace(' ', '_')
    try:
        chapter_val = float(chapter_num)
    except (ValueError, TypeError):
        chapter_val = 0.0
        
    print(f"  [VECTORS] Indexando resumen del Capítulo {chapter_num} de {manga_name} en ChromaDB...")
    
    try:
        # Generar embedding del resumen
        embedding = generar_embedding(resumen)
        
        # Obtener colección
        collection = get_collection()
        
        # Guardar en ChromaDB
        doc_id = f"{manga_key}_cap_{chapter_num}"
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[resumen],
            metadatas=[{
                "manga": manga_key,
                "chapter": chapter_val
            }]
        )
        print(f"  [VECTORS] [OK] Resumen del Capítulo {chapter_num} indexado con éxito (ID: {doc_id}).")
        return True
    except Exception as e:
        print(f"  [VECTORS] [ERROR] No se pudo guardar el resumen en ChromaDB: {e}")
        return False

def obtener_contexto_historico(manga_name, chapter_num, prompt_consulta, top_k=3):
    """
    Busca semánticamente en ChromaDB los eventos y resúmenes pasados de un manga
    y retorna un string concatenado del contexto relevante.
    """
    manga_key = manga_name.replace(' ', '_')
    try:
        chapter_val = float(chapter_num)
    except (ValueError, TypeError):
        chapter_val = 0.0

    print(f"  [VECTORS] Buscando contexto de lore para {manga_name} (Cap {chapter_num}) en ChromaDB...")
    
    try:
        # 1. Generar embedding de la consulta
        query_embedding = generar_embedding(prompt_consulta)
        
        # 2. Obtener la colección
        collection = get_collection()
        
        # 3. Realizar búsqueda con filtro de metadatos (mismo manga, capítulos anteriores)
        # ChromaDB query acepta where para filtrar
        where_filter = {
            "$and": [
                {"manga": {"$eq": manga_key}},
                {"chapter": {"$lt": chapter_val}}
            ]
        }
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter
        )
        
        # 4. Formatear y construir contexto histórico
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        
        if not documents:
            print("  [VECTORS] No se encontró historia o contexto previo en la base vectorial.")
            return ""
            
        print(f"  [VECTORS] [OK] Recuperados {len(documents)} bloques de contexto histórico.")
        
        context_blocks = []
        # Ordenar los resultados recuperados de menor a mayor capítulo para flujo cronológico
        combined = list(zip(metadatas, documents))
        combined_sorted = sorted(combined, key=lambda x: x[0].get("chapter", 0.0))
        
        for meta, doc in combined_sorted:
            cap = meta.get("chapter")
            context_blocks.append(f"- Del Capítulo {cap}: {doc}")
            
        return "\n".join(context_blocks)
        
    except Exception as e:
        print(f"  [VECTORS] [AVISO] Error al consultar contexto histórico: {e}")
        return ""
