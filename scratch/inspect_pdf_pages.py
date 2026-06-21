import fitz

pdf_path = r"c:\Users\ignacio\Desktop\Nueva carpeta (2)\end to end\Proyecto manga recap\pdf_storage\Single_Dad_In_Another_World\Capitulo_1.pdf"
doc = fitz.open(pdf_path)

print(f"Total pages in PDF: {len(doc)}")
for i in range(55, len(doc)):
    page = doc.load_page(i)
    text = page.get_text().strip()
    rect = page.rect
    print(f"Page {i+1}: Text Length: {len(text)}, Dimensions: {rect.width}x{rect.height}")
    if text:
        print(f"  Snippet: {text[:100]}")
