import re

with open("templates/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# Search for styling blocks or inline styles that might affect library-card or library-grid
matches = []
for i, line in enumerate(content.splitlines(), 1):
    if "library" in line or "card" in line or "grid" in line:
        matches.append((i, line.strip()))

print(f"Found {len(matches)} occurrences:")
for idx, line in matches[:100]:  # Limit print
    print(f"Line {idx}: {line}")
