import os
import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfReader
import google.genai as genai
from google.genai import types
import json


def extract_text_from_pdf(pdf_path):
    """Extrahiert Text direkt oder via OCR, falls kein Text gefunden wurde."""
    reader = PdfReader(pdf_path)
    text = ""
    
    # Versuche zuerst, eingebetteten Text zu lesen
    for page in reader.pages:
        text += page.extract_text() or ""
    
    # Wenn fast kein Text gefunden wurde (Bild-PDF), nutze OCR
    if len(text.strip()) < 20:
        print(f"OCR wird gestartet für: {pdf_path}")
        images = convert_from_path(pdf_path)
        text = ""
        for img in images:
            # 'deu' für deutsche Texterkennung (muss installiert sein)
            text += pytesseract.image_to_string(img, lang='deu')
            
    return text

def classify_and_extract(text):
    """Nutzt Google Gemini 2.5 Flash, um das Dokument zu analysieren."""
    prompt = f"""
    Analysiere den folgenden Text eines Dokuments und extrahiere Informationen im JSON-Format.
    Kategorien: Rechnung, Gehaltsabrechnung, Versicherung, Vertrag, Sonstiges.    Antworte sehr präzise, validiere die Ausgabe und gib nur gültiges JSON zurück.
    Text:
    {text[:2000]}

    Antworte NUR mit validem JSON in diesem Format:
    {{
        "typ": "Kategorie",
        "datum": "YYYY-MM-DD",
        "absender": "Name der Firma",
        "betreff": "Kurze Zusammenfassung"
    }}
    """

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        raise RuntimeError("GEMINI_API_KEY oder GOOGLE_API_KEY muss gesetzt sein")

    client = genai.Client(api_key=gemini_key)
    model_name = "gemini-2.5-flash"

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=512,
            temperature=0.0,
            top_p=1.0
        )
    )

    raw_output = ""
    if hasattr(response, "text") and response.text:
        raw_output = str(response.text).strip()
    elif hasattr(response, "parts") and response.parts:
        part_texts = [
            p.get("text", "") if isinstance(p, dict) else getattr(p, "text", "")
            for p in response.parts
        ]
        raw_output = " ".join(filter(None, part_texts)).strip()
    else:
        raise ValueError("Keine gültige Ausgabe von Gemini erhalten")

    # Handhabe Code-Fencing (```json ... ```)
    if raw_output.startswith("```"):
        parts = raw_output.split("\n")
        if parts[0].startswith("```"):
            parts = parts[1:]
        if parts and parts[-1].strip().endswith("```"):
            parts = parts[:-1]
        raw_output = "\n".join(parts).strip()

    # Ggf. mit JSON umgeben, falls Gemini strukturiert umsäumt liefert
    metadata = None
    try:
        metadata = json.loads(raw_output)
    except json.JSONDecodeError:
        start = raw_output.find('{')
        if start == -1:
            # Keine JSON-Struktur erkennbar, Rückgabe mit default
            return {"typ": "Sonstiges", "datum": "", "absender": "", "betreff": ""}

        candidate = raw_output[start:]
        # Wenn nur unvollständiges JSON geliefert wird, versuchen wir noch, schließende Klammern hinzuzufügen
        if '}' not in candidate:
            candidate += '}'

        end = candidate.rfind('}') + 1
        if end <= 0:
            return {"typ": "Sonstiges", "datum": "", "absender": "", "betreff": ""}

        candidate = candidate[:end]
        normalized = candidate.replace("'", '"').replace(',}', '}').replace(',]', ']')

        try:
            metadata = json.loads(normalized)
        except json.JSONDecodeError:
            # Fallback auf default, da kein valides JSON
            return {"typ": "Sonstiges", "datum": "", "absender": "", "betreff": ""}

    if not metadata or not isinstance(metadata, dict):
        return {"typ": "Sonstiges", "datum": "", "absender": "", "betreff": ""}

    return {
        "typ": metadata.get("typ") or metadata.get("type") or "Sonstiges",
        "datum": metadata.get("datum") or metadata.get("date") or "",
        "absender": metadata.get("absender") or metadata.get("sender") or metadata.get("from") or "",
        "betreff": metadata.get("betreff") or metadata.get("subject") or ""
    }

# Beispiel Testlauf:
# doc_text = extract_text_from_pdf("data/output/split_doc_1.pdf")
# metadata = classify_and_extract(doc_text)
# print(metadata)