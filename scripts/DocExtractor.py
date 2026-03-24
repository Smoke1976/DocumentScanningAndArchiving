import os
from dotenv import load_dotenv
import google.generativeai as genai
from pypdf import PdfReader

# 1. Setup
load_dotenv() # Lädt API Key aus .env Datei
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def analyze_document(pdf_path):
    # Text aus der ersten Seite extrahieren (einfaches Beispiel)
    reader = PdfReader(pdf_path)
    first_page_text = reader.pages[0].extract_text()
    
    # Prompt für die KI
    prompt = f"""
    Analysiere diesen Text eines Dokuments:
    {first_page_text}
    
    Gib mir ein JSON zurück mit:
    - type (z.B. Rechnung, Gehaltsabrechnung, Versicherung)
    - date (YYYY-MM-DD)
    - sender (Name der Firma/Person)
    - subject (Kurzer Betreff)
    """
    
    response = model.generate_content(prompt)
    return response.text

# Beispielaufruf
# print(analyze_document("data/input/scan_001.pdf"))