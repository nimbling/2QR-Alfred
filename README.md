# 2qr — Alfred QR Code Generator (Vector-first)

This workflow wraps the **Nayuki QR Code generator** in an Alfred keyword.
It lets you type:

```
2qr https://example.com
```

Then it offers optional interactive prompts for:
- Error correction: Low / Medium / Quartile / High (default High)
- Output format: Vector (SVG) or Bitmap (PNG) — default Vector
- For **Vector**: Border (modules), Light/Dark colors (#RRGGBB), Version range min/max
- For **Bitmap**: Border (modules), Scale (pixels per module)

The file is saved to `~/Desktop/QR-YYYYMMDD-HHMMSS.svg` or `.png`.
The script shows a notification and opens the file in Finder.

## Install steps

1) Download `qrcodegen.py` from the Nayuki repo and place it next to `main.py` in this folder.
   Repo: https://github.com/nayuki/QR-Code-generator  (python/ subfolder)

2) In Alfred:
   - Preferences → Workflows → + → **Blank Workflow**
   - Name: `2qr – QR Code`
   - Add an **Input → Keyword** node.
     - Keyword: `2qr`
     - with space: checked
     - Argument required: checked
     - Title/Subtitle: as you like
     - In the keyword node, choose **Action → Run Script**:
       - Language: `/bin/bash`
       - Script:
         ```bash
         /usr/bin/python3 "$PWD/main.py" "{query}"
         ```
       - Ensure `main.py` and `qrcodegen.py` are inside the workflow folder
         (right‑click the workflow → *Open in Finder* and copy both files there).

3) Test: In Alfred, type `2qr https://example.com` and press Enter.
   Choose options or accept defaults. The QR will appear on your Desktop.

## Notes
- Hex colors must be in `#RRGGBB` form.
- Version range: integers 1–40 inclusive.
- Canceling any dialog keeps the default value.
- The script never sends data to the network.
