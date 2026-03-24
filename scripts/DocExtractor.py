import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfReader
import ollama
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
    """Nutzt Ollama (Mistral), um das Dokument zu analysieren."""
    prompt = f"""
    Analysiere den folgenden Text eines Dokuments und extrahiere Informationen im JSON-Format.
    Kategorien: Rechnung, Gehaltsabrechnung, Versicherung, Vertrag, Sonstiges.
    
    Text:
    {text[:2000]}  # Wir nehmen die ersten 2000 Zeichen zur Analyse
    
    Antworte NUR mit validem JSON in diesem Format:
    {{
        "typ": "Kategorie",
        "datum": "YYYY-MM-DD",
        "absender": "Name der Firma",
        "betreff": "Kurze Zusammenfassung"
    }}
    """
    text_shortened = text[:400]
    response = ollama.generate(
        model='qwen2:0.5b', # Wechsel auf das kleine Modell
        prompt=f"Dokumenten-Text: {text_shortened}\nAntworte im JSON-Format: {{'typ': '...', 'datum': '...', 'sender': '...'}}",
        options={
            "num_thread": 4,   # Nutze nur 4 Kerne, damit Kali benutzbar bleibt
            "num_predict": 64,  # Sehr kurze Antwort erzwingen
            "temperature": 0
        }
    )
    
    # Bereinigung, falls die KI Text um das JSON herum baut
    raw_output = response['response'].strip()

    # Direktversuch: volle Ausgabe parsen
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        pass

    # Extrahiere erstes JSON-Objekt
    start = raw_output.find('{')
    end = raw_output.rfind('}') + 1
    if start == -1 or end == 0 or start >= end:
        raise ValueError(f"Keine JSON-Struktur im Output gefunden: {raw_output!r}")

    candidate = raw_output[start:end]

    # Versuch 2: Nächstes JSON aus dem Text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        # Versuch mit einfachen Konversionen (z.B. Single-Quotes)
        normalized = candidate.replace("'", '"')

        # Entferne trailing commas
        normalized = normalized.replace(',}', '}').replace(',]', ']')

        try:
            metadata = json.loads(normalized)
        except json.JSONDecodeError:
            raise ValueError(
                f"JSON konnte nicht geparst werden: {e}. Rohoutput: {raw_output!r}. Kandidat: {candidate!r}. Normalisiert: {normalized!r}"
            )

    # Vereinheitliche Feldnamen und fehlende Werte
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