import sys
import os

# Asegurar que se puede importar modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import pdf_converter

manga_name = "A_Sword_Master_Childhood_Friend_Power_Harassed_Me_Harshly_So_I_Broke_Off_Our_Relationship_And_Make_A_Fresh_Start_At_The_Frontier_As_A_Magic_Swordsman"
chapters_to_process = ["Capitulo_25.1", "Capitulo_25.2", "Capitulo_25.3"]

print("Ejecutando conversión de prueba...")
result = pdf_converter.convert_webp_to_pdf(manga_name, chapters_to_process)
print(f"Resultado de la conversión: {result} PDFs creados.")
