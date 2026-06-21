import fitz
import os

pdf_path = r"c:\Users\ignacio\Desktop\Nueva carpeta (2)\end to end\Proyecto manga recap\pdf_storage\Single_Dad_In_Another_World\Capitulo_1.pdf"
doc = fitz.open(pdf_path)

output_dir = r"c:\Users\ignacio\Desktop\Nueva carpeta (2)\end to end\Proyecto manga recap\scratch\pdf_pages"
os.makedirs(output_dir, exist_ok=True)

pages_to_check = [57, 58, 65, 70, 74]  # 0-indexed: pages 58, 59, 66, 71, 75
for p in pages_to_check:
    if p < len(doc):
        page = doc.load_page(p)
        pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2))  # small scale
        img_path = os.path.join(output_dir, f"page_{p+1}.png")
        pix.save(img_path)
        print(f"Saved page {p+1} to {img_path}")
