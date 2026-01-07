#!/usr/bin/env python3
"""
Konvertiert SVG Sudoku-Rätsel und deren Lösungen in ein formatiertes PDF-Dokument.
Rätsel und Lösungen werden auf abwechselnden Seiten angeordnet.

Anforderungen:
- pip install reportlab pillow
- ImageMagick (convert Befehl) muss installiert sein

Dateinamenskonvention:
- sudoku6x6-3-XXXX-puzzle.svg   (das leere Rätsel)
- sudoku6x6-3-XXXX-solution.svg (die Lösung)
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from io import BytesIO
    from PIL import Image
    import xml.etree.ElementTree as ET
except ImportError as e:
    print(f"Fehler: Erforderliche Bibliothek nicht installiert.")
    print("Installiere mit: pip install reportlab pillow")
    sys.exit(1)

PAGE_TITLE = "Jigsaw Sudoku"

# NEU: KDP-Seitengröße 13,97 cm x 21,59 cm (5.5" x 8.5") in Punkten (1in = 72pt)
KDP_PAGE_SIZE = (396.0, 612.0)  # (width_pt, height_pt)


def find_puzzle_pairs(directory: str) -> List[Tuple[str, str, str]]:
    """
    Findet alle Puzzle-Lösungs-Paare im Verzeichnis.

    Returns:
        Liste von Tupeln: (base_name, puzzle_path, solution_path)
    """
    puzzle_files = {}
    solution_files = {}

    # Finde alle Dateien
    for filename in os.listdir(directory):
        if not filename.endswith(".svg"):
            continue

        match = re.match(r"(.+)-puzzle\.svg$", filename)
        if match:
            base_name = match.group(1)
            puzzle_files[base_name] = os.path.join(directory, filename)
            continue

        match = re.match(r"(.+)-solution\.svg$", filename)
        if match:
            base_name = match.group(1)
            solution_files[base_name] = os.path.join(directory, filename)

    # Paare zusammenführen
    pairs = []
    for base_name in sorted(puzzle_files.keys()):
        if base_name in solution_files:
            pairs.append(
                (base_name, puzzle_files[base_name], solution_files[base_name])
            )

    return pairs


def svg_to_png(svg_path: str, width: int = 1800, dpi: int = 300) -> Image.Image:
    """
    Konvertiert eine SVG-Datei zu einem PIL Image mittels ImageMagick mit hoher Auflösung.

    Args:
        svg_path: Pfad zur SVG-Datei
        width: Zielbreite in Pixeln (Standard: 1800 für hohe Auflösung)
        dpi: DPI-Einstellung für die Konvertierung (Standard: 300 für Druck)

    Returns:
        PIL Image Objekt
    """
    import subprocess

    try:
        png_bytes = BytesIO()
        result = subprocess.run(
            [
                "convert",
                f"-density",
                f"{dpi}x{dpi}",  # Höhere Auflösung
                svg_path,
                "-background",
                "white",
                "-flatten",  # Flache das Bild ab
                "-quality",
                "95",  # Hohe Qualität
                "png:-",
            ],
            capture_output=True,
            timeout=15,
        )

        if result.returncode == 0 and result.stdout:
            png_bytes.write(result.stdout)
            png_bytes.seek(0)
            img = Image.open(png_bytes).convert("RGB")
            img.load()  # Lade das Bild vor dem Zurückgeben
            return img
        else:
            print(
                f"  ⚠ ImageMagick Fehler: {result.stderr.decode() if result.stderr else 'Unbekannt'}"
            )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  ⚠ Fehler bei SVG-Konvertierung: {e}")

    try:
        from pdf2image import convert_from_path
        from pdf2image.exceptions import PDFPageCountError
        import tempfile
        import subprocess

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf_path = tmp_pdf.name

        try:
            subprocess.run(
                ["rsvg-convert", svg_path, "-o", tmp_pdf_path], check=True, timeout=10
            )

            images = convert_from_path(tmp_pdf_path)
            if images:
                return images[0]
        finally:
            if os.path.exists(tmp_pdf_path):
                os.remove(tmp_pdf_path)
    except:
        pass

    print(f"  ⚠ Warnung: Kann SVG nicht konvertieren, verwende Placeholder")
    img = Image.new("RGB", (800, 800), color="white")
    return img


def get_image_dimensions(svg_path: str) -> Tuple[float, float]:
    """
    Extrahiert die Dimensionen einer SVG-Datei.
    """
    import xml.etree.ElementTree as ET

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()

        # Namespaces verarbeiten
        ns = {"svg": "http://www.w3.org/2000/svg"}

        # Versuche width/height Attribute zu finden
        width = root.get("width", "200")
        height = root.get("height", "200")

        # Entferne Units (px, cm, etc.)
        width = float(
            re.search(r"\d+", width).group() if re.search(r"\d+", width) else 200
        )
        height = float(
            re.search(r"\d+", height).group() if re.search(r"\d+", height) else 200
        )

        return (width, height)
    except Exception:
        return (200, 200)


def create_pdf_with_puzzles(
    directory: str, output_file: str = "sudoku_puzzles.pdf", pagesize=A4
):
    """
    Erstellt ein PDF mit Rätseln und Lösungen auf abwechselnden Seiten.
    pagesize: Tuple(width_pt, height_pt) oder reportlab.pagesizes (Default: A4)
    """
    import tempfile

    pairs = find_puzzle_pairs(directory)

    if not pairs:
        print(f"Fehler: Keine Puzzle-Lösungs-Paare in '{directory}' gefunden.")
        print("Erwartet: *-puzzle.svg und *-solution.svg Dateien")
        return

    print(f"Gefundene Paare: {len(pairs)}")
    for base_name, _, _ in pairs:
        print(f"  - {base_name}")

    # Erstelle temporäres Verzeichnis
    temp_dir = tempfile.mkdtemp()

    # PDF erstellen
    pdf_canvas = canvas.Canvas(output_file, pagesize=pagesize)

    width, height = pagesize
    margin = 1 * cm

    # Optimale Bildgröße für A4 (mit Margins)
    max_image_width = width - 2 * margin
    max_image_height = height - 3 * cm  # Mehr Platz oben für Titel

    page_count = 0

    try:
        # Verarbeite jedes Puzzle-Lösungs-Paar
        for base_name, puzzle_path, solution_path in pairs:

            # ========== PUZZLE SEITE ==========
            page_count += 1
            print(f"\nSeite {page_count}: {base_name} (Puzzle)")

            try:
                # SVG zu PNG konvertieren
                puzzle_img = svg_to_png(puzzle_path, width=800)

                # Berechne Skalierung
                img_width, img_height = puzzle_img.size
                scale = min(max_image_width / img_width, max_image_height / img_height)

                display_width = img_width * scale
                display_height = img_height * scale

                # Zentriere Bild horizontal
                x = (width - display_width) / 2
                y = height - margin - display_height - 1.5 * cm

                # Speichere temporäres PNG mit eindeutigem Namen
                temp_image = os.path.join(temp_dir, f"{base_name}_puzzle.png")
                puzzle_img.save(temp_image, "PNG")

                # Titel
                pdf_canvas.setFont("Helvetica-Bold", 16)
                pdf_canvas.drawString(margin, height - margin - 0.5 * cm, PAGE_TITLE)

                # Bild
                pdf_canvas.drawImage(
                    temp_image, x, y, width=display_width, height=display_height
                )

                pdf_canvas.showPage()

            except Exception as e:
                print(f"  Fehler beim Verarbeiten von {puzzle_path}: {e}")

            # ========== LÖSUNG SEITE ==========
            page_count += 1
            print(f"Seite {page_count}: {base_name} (Lösung)")

            try:
                # SVG zu PNG konvertieren
                solution_img = svg_to_png(solution_path, width=800)

                # Berechne Skalierung
                img_width, img_height = solution_img.size
                scale = min(max_image_width / img_width, max_image_height / img_height)

                display_width = img_width * scale
                display_height = img_height * scale

                # Zentriere Bild horizontal
                x = (width - display_width) / 2
                y = height - margin - display_height - 1.5 * cm

                # Speichere temporäres PNG mit eindeutigem Namen
                temp_image = os.path.join(temp_dir, f"{base_name}_solution.png")
                solution_img.save(temp_image, "PNG")

                # Titel
                pdf_canvas.setFont("Helvetica-Bold", 16)
                pdf_canvas.drawString(
                    margin, height - margin - 0.5 * cm, "Solution / Lösung"
                )

                # Bild
                pdf_canvas.drawImage(
                    temp_image, x, y, width=display_width, height=display_height
                )

                pdf_canvas.showPage()

            except Exception as e:
                print(f"  Fehler beim Verarbeiten von {solution_path}: {e}")

        # PDF speichern
        pdf_canvas.save()
        print(f"\n✓ PDF erfolgreich erstellt: {output_file}")
        print(f"  Seiten gesamt: {page_count}")

    finally:
        # Cleanup: Lösche temporäre Dateien
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    # Verzeichnis als Kommandozeilenargument oder aktuelles Verzeichnis
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    output_file = sys.argv[2] if len(sys.argv) > 2 else "sudoku_puzzles.pdf"
    pagesize_arg = sys.argv[3] if len(sys.argv) > 3 else "A4"

    # Kurze Seitenauswahl: "kdp" -> 13,97cm x 21,59cm; "A4" -> A4
    if pagesize_arg.lower() in ("kdp", "5.5x8.5", "5.5x8.5in"):
        pagesize = KDP_PAGE_SIZE
    else:
        pagesize = A4

    if not os.path.isdir(directory):
        print(f"Fehler: Verzeichnis '{directory}' nicht gefunden.")
        sys.exit(1)

    create_pdf_with_puzzles(directory, output_file, pagesize=pagesize)
