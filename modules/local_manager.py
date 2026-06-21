from modules import database

def verificar_manga_local(manga_id):
    manga = database.obtener_manga(manga_id)
    if manga:
        return {
            "existe": True,
            "titulo": manga[1],
            "total_caps": manga[3]
        }
    return {"existe": False}

def requiere_descarga(chapter_id):
    descargado = database.capitulo_esta_descargado(chapter_id)
    return not descargado

def listar_mangas_registrados():
    conn = database.conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM mangas')
    lista = cursor.fetchall()
    conn.close()
    return lista

def manga_esta_descargado(manga_id):
    conn = database.conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM capitulos WHERE manga_id = ? AND descargado = 1', (manga_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0