import os
import fitz

pdf_base = r"c:\Users\ignacio\Desktop\Nueva carpeta (2)\end to end\Proyecto manga recap\pdf_storage"
data = []

print("--- Analyzing all PDFs in pdf_storage ---")
for root, dirs, files in os.walk(pdf_base):
    for f in files:
        if f.endswith(".pdf"):
            full_path = os.path.join(root, f)
            manga_name = os.path.basename(os.path.dirname(full_path))
            try:
                doc = fitz.open(full_path)
                page_count = len(doc)
                doc.close()
                data.append({
                    "manga": manga_name,
                    "filename": f,
                    "pages": page_count
                })
                print(f"Manga: {manga_name} | File: {f} | Pages: {page_count}")
            except Exception as e:
                print(f"Error reading {full_path}: {e}")

print("\n--- Summary by Manga ---")
manga_summaries = {}
for entry in data:
    m = entry["manga"]
    if m not in manga_summaries:
        manga_summaries[m] = []
    manga_summaries[m].append(entry["pages"])

for m, pages in sorted(manga_summaries.items()):
    avg_pages = sum(pages) / len(pages)
    min_pages = min(pages)
    max_pages = max(pages)
    total_files = len(pages)
    print(f"Manga: {m}")
    print(f"  Chapters count: {total_files}")
    print(f"  Page range: {min_pages} - {max_pages} pages")
    print(f"  Average pages per chapter: {avg_pages:.1f}")

total_pages_all = sum(entry["pages"] for entry in data)
total_chapters = len(data)
if total_chapters > 0:
    print(f"\nOverall Statistics:")
    print(f"  Total chapters: {total_chapters}")
    print(f"  Total pages across all PDFs: {total_pages_all}")
    print(f"  Average pages per chapter overall: {total_pages_all / total_chapters:.1f}")
