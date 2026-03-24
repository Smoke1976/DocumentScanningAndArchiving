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
    
    response = ollama.generate(model='mistral', prompt=prompt)
    
    # Bereinigung, falls die KI Text um das JSON herum baut
    raw_output = response['response']
    start = raw_output.find('{')
    end = raw_output.rfind('}') + 1
    return json.loads(raw_output[start:end])

# Beispiel Testlauf:
# doc_text = extract_text_from_pdf("data/output/split_doc_1.pdf")
# metadata = classify_and_extract(doc_text)
# print(metadata)