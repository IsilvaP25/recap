import sqlite3
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(base_dir, 'database', 'manga_recap.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get manga id for this manga
cursor.execute('SELECT id, titulo FROM mangas WHERE titulo LIKE "%Sword_Master%" OR titulo LIKE "%Sword Master%"')
mangas = cursor.fetchall()
print("Mangas encontrados:")
for m in mangas:
    print(m)
    m_id = m[0]
    cursor.execute('SELECT id, titulo, descargado, pasado_a_pdf FROM capitulos WHERE manga_id = ? LIMIT 20', (m_id,))
    caps = cursor.fetchall()
    print("Capítulos (primeros 20):")
    for c in caps:
        print(c)
    
    # Check if there are chapters like 25.1 or 26.1
    cursor.execute('SELECT id, titulo, descargado, pasado_a_pdf FROM capitulos WHERE manga_id = ? AND (titulo LIKE "%25%" OR titulo LIKE "%26%" OR titulo LIKE "%27%")', (m_id,))
    decimal_caps = cursor.fetchall()
    print("Capítulos decimales:")
    for dc in decimal_caps:
        print(dc)

conn.close()
