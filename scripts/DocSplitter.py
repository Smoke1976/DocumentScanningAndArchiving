import os
import re
import time
import pytesseract
from PIL import ImageStat
from pdf2image import convert_from_path
import google.genai as genai
from google.genai import types
from pypdf import PdfReader, PdfWriter


def is_new_doc_gemini(text_chunk):
    """Prüft mit Google Gemini, ob eine neue Seite beginnt."""

    prompt = (
        "Du bist ein Dokumenten-Assistent. Analysiere den Textanfang einer Seite aus einem mehrseitigen PDF.\n"
        "Paginierung und Fortsetzungen desselben Dokuments sind NORMAL.\n"
        "Ist dies der START eines NEUEN, VÖLLIG ANDEREN Dokuments (z.B. neue Rechnung statt alte, neuer Vertrag statt alte)?\n"
        f"Text: {text_chunk[:600]}\n"
        "Antworte NUR mit 'JA' (neues Dokument) oder 'NEIN' (Fortsetzung)."
    )

    # Prüfe, ob Gemini API Key verfügbar ist
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        raise RuntimeError("GEMINI_API_KEY oder GOOGLE_API_KEY ist nicht gesetzt. Kein Qwen-Fallback gewünscht.")

    try:
        client = genai.Client(api_key=gemini_key)

        # Modell 2.5 Flash verwenden
        model_name = 'gemini-2.5-flash'

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=8,
                temperature=0.0
            )
        )

        # Response kann text haben oder in parts, robust auswerten
        result = ''
        if hasattr(response, 'text') and response.text:
            result = str(response.text)
        elif hasattr(response, 'parts') and response.parts:
            # parts kann z.B. [{'type':'output_text','text':'...'}]
            part_texts = [p.get('text','') if isinstance(p, dict) else getattr(p, 'text', '') for p in response.parts]
            result = ' '.join(filter(None, part_texts))

        result = result.strip().upper()

        if "JA" in result:
            return True
        if "NEIN" in result:
            return False

        # Wenn die KI Dinge wie 'Sollte JA sein' zurückgibt, robust parsen
        if "YES" in result:
            return True
        if "NO" in result:
            return False

        # Wenn unklar, als kein neuer Abschnitt (sichere Haltung)
        return False
    except Exception as e:
        error_msg = str(e)
        # Handle transient service errors with retries
        if "503" in error_msg or "UNAVAILABLE" in error_msg:
            # maximal 3 Versuche, danach für diese Seite als Nicht-Neuanfang behandeln
            is_new_doc_gemini._retry_count = getattr(is_new_doc_gemini, '_retry_count', 0) + 1
            if is_new_doc_gemini._retry_count <= 3:
                wait_seconds = 2 ** is_new_doc_gemini._retry_count
                print(f"Gemini temporär nicht verfügbar (503), retry in {wait_seconds}s...")
                time.sleep(wait_seconds)
                return is_new_doc_gemini(text_chunk)
            else:
                print("Gemini weiterhin nicht verfügbar, nach 3 Versuchen auf False setzen")
                is_new_doc_gemini._retry_count = 0
                return False

        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
            # falls Rate-Limit-Fehler, (benutzerwunsch: kein qwen fallback)
            print(f"Gemini Rate-Limit erreicht: {e}")
            return False

        print(f"Gemini API Fehler (evtl. Modellname falsch oder Limit erreicht): {e}")
        return False


def _text_for_page(reader, page_index, pdf_path):
    page = reader.pages[page_index]
    text = page.extract_text() or ""

    if len(text.strip()) < 20:
        # Bild-PDF oder kein eingebetteter Text: benutze OCR-Seite
        print(f"OCR für Seite {page_index+1} wegen textarmer Seite")
        try:
            images = convert_from_path(pdf_path, first_page=page_index+1, last_page=page_index+1)
        except Exception as e:
            print(f"OCR-Konvertierung fehlgeschlagen auf Seite {page_index+1}: {e}")
            return text

        ocr_text = ""
        for img in images:
            try:
                ocr_text += pytesseract.image_to_string(img, lang='deu')
            except Exception as e:
                print(f"OCR fehlgeschlagen auf Seite {page_index+1}: {e}")
                continue
        if ocr_text.strip():
            text = ocr_text

    return text


def _extract_metadata_from_text(text):
    """Extrahiere Datum, Seitennummer und Absender aus Dokumenttext."""
    data = {
        "date": None,
        "page_num": None,
        "sender": None
    }

    # Datumsformate: DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY
    date_patterns = [
        r'\d{1,2}\.\d{1,2}\.\d{4}',
        r'\d{4}-\d{2}-\d{2}',
        r'\d{1,2}/\d{1,2}/\d{4}'
    ]
    for pat in date_patterns:
        m = re.search(pat, text)
        if m:
            data["date"] = m.group(0)
            break

    # Seitennummer: "Seite X von Y" oder "Page X of Y"
    page_patterns = [
        r'seite\s+(\d+)\s+von\s+(\d+)',
        r'page\s+(\d+)\s+of\s+(\d+)',
        r'seite\s+(\d+)\s*$',
        r'page\s+(\d+)\s*$'
    ]
    for pat in page_patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            data["page_num"] = m.group(1)
            break

    # Absender: Erste Zeile mit Firmennamen-Mustern
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) > 0:
        # Suche nach Firma (GmbH, AG, etc.) in den ersten 5 Zeilen
        for line in lines[:5]:
            if re.search(r'\b(GmbH|AG|UG|OHG|KG|e\.V\.|GmbH & Co\.)', line, re.IGNORECASE):
                data["sender"] = line[:60]  # erste 60 Zeichen
                break

    return data


def _metadata_changed(prev_meta, curr_meta):
    """Prüfe ob kritische Metadaten sich geändert haben (Indiz für Dokumentwechsel)."""
    if not prev_meta or not curr_meta:
        return False

    # Datumsänderung ist sehr starker Indikator
    if prev_meta.get("date") and curr_meta.get("date"):
        if prev_meta["date"] != curr_meta["date"]:
            return True

    # Seitennummern-Reset: z.B. von "Seite 5" zu "Seite 1"
    if prev_meta.get("page_num") and curr_meta.get("page_num"):
        prev_page = int(prev_meta["page_num"])
        curr_page = int(curr_meta["page_num"])
        if curr_page <= prev_page:  # Seite ist zurückgesprungen oder gleich
            return True

    # Absenderwechsel ist sehr starker Indikator
    if prev_meta.get("sender") and curr_meta.get("sender"):
        if prev_meta["sender"] != curr_meta["sender"]:
            return True

    return False


def _layout_changed(prev_text, curr_text):
    """Grobe Layout-Änderung anhand Zeilenanzahl und Strukturunterschiede erkennen.
    Bewusst SEHR konservativ für gescannte PDFs, wo OCR-Variation normal ist."""
    if not prev_text or not curr_text:
        return False

    prev_lines = [l for l in prev_text.splitlines() if l.strip()]
    curr_lines = [l for l in curr_text.splitlines() if l.strip()]
    if not prev_lines or not curr_lines:
        return False

    # Extreme Textlängenänderung - erhöht auf 100 (Mehrseiter sollten stabil sein)
    if abs(len(curr_lines) - len(prev_lines)) > 100:
        return True

    # Layout-Änderung nur bei EXTREMEM Unterschied - erhöht auf 200%
    def avg_line_len(lines):
        return float(sum(len(l) for l in lines)) / max(1, len(lines))

    prev_len = avg_line_len(prev_lines)
    curr_len = avg_line_len(curr_lines)
    if prev_len > 0 and abs(curr_len - prev_len) / prev_len > 2.0:
        return True

    # Titel/Überschriftenwechsel - nur bei DEUTLICHEN neuen Dokumenttypen
    heading_re = re.compile(r'^(rechnung|vertrag|angebot|bestellung|lieferschein|rechnung nr\.|rechnungsnummer|quittung)', re.IGNORECASE)
    prev_has_heading = bool(heading_re.match(prev_lines[0]))
    curr_has_heading = bool(heading_re.match(curr_lines[0]))
    if not prev_has_heading and curr_has_heading:
        return True

    return False


def _is_new_doc_graphical(pdf_path, page_index):
    """Entscheidet anhand der Bildstruktur eines Seitenanfangs, ob ein neuer Dokumentstart vorliegt.
    Bei gescannten PDFs sehr konservativ, da Bildvarianz jede Seite anders aussehen kann."""
    try:
        image = convert_from_path(pdf_path, first_page=page_index+1, last_page=page_index+1)[0]
    except Exception:
        return False

    w, h = image.size
    top_height = int(min(0.2 * h, 250))
    top_region = image.crop((0, 0, w, top_height)).convert("L")

    stat = ImageStat.Stat(top_region)
    # Sehr hohe Standardabweichung nötig (war 40, jetzt 60) - nur starke Header-Änderungen
    if stat.stddev[0] > 60:
        return True

    # Sehr hoher Schwarz-Anteil nötig (war 0.25, jetzt 0.4) - nur massive Header-Elemente
    black_ratio = sum(1 for px in top_region.getdata() if px < 80) / float(w * top_height)
    if black_ratio > 0.4:
        return True

    return False


def split_pdf_gemini_hybrid(input_pdf_path, output_folder):
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    doc_count = 1
    prev_text = None
    prev_meta = None

    for i in range(len(reader.pages)):
        text = _text_for_page(reader, i, input_pdf_path)

        if i == 0:
            is_new = True
        else:
            is_new = False
            reason = ""

            # 1. Metadaten-Wechsel (sehr zuverlässig)
            curr_meta = _extract_metadata_from_text(text)
            if prev_meta and _metadata_changed(prev_meta, curr_meta):
                is_new = True
                reason = "Metadaten-Wechsel"

            # 2. Layout-Änderung (konservativ)
            if not is_new:
                is_new = _layout_changed(prev_text, text)
                if is_new:
                    reason = "Layout-Wechsel"

            # 3. Visuelle Änderung (Grafik)
            if not is_new:
                is_new = _is_new_doc_graphical(input_pdf_path, i)
                if is_new:
                    reason = "Visuelle Änderung"

            # 4. Gemini-KI als letzte Instanz
            if not is_new:
                is_new = is_new_doc_gemini(text)
                if is_new:
                    reason = "Gemini: JA"
                else:
                    reason = "Nein"

            print(f"Seite {i+1}: is_new={is_new} ({reason})")

        if is_new and i > 0:
            save_pdf(writer, output_folder, doc_count)
            writer = PdfWriter()
            doc_count += 1

        writer.add_page(reader.pages[i])
        prev_text = text
        prev_meta = _extract_metadata_from_text(text)

    save_pdf(writer, output_folder, doc_count)


def save_pdf(writer, folder, count):
    path = os.path.join(folder, f"doc_{count}.pdf")
    with open(path, "wb") as f:
        writer.write(f)