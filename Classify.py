import os
import re
import fitz  # PyMuPDF
import json
from pathlib import Path
import google.generativeai as genai
from pydantic import BaseModel, Field
import pytesseract
import shutil
from pdf2image import convert_from_path
from pathlib import Path


# --- KONFIGURATION ---
API_KEY = "AIzaSyCpT1O-FYohWSCX_7caYaxTzijgSTeyFTI"
INPUT_DIR = Path(r"\\192.168.178.27\Network-Exchange-Folder\TOSHIBA-MQ04ABD200-01\HP_MFW4302_Scans")
OUTPUT_DIR = Path(r"C:\Users\Tobias\OneDrive\Scans")

genai.configure(api_key=API_KEY)


# Struktur für die KI-Antwort definieren
class DocumentInfo(BaseModel):
    datum: str = Field(description="Datum im Format YYYY-MM-DD")
    absender: str = Field(
        description="Name des Absenders, kurz und ohne Sonderzeichen"
    )
    klassifizierung: str = Field(
        description="Kategorie des Dokuments (z.B. Rechnung, Vertrag)"
    )
    summary: str = Field(
        description="Kurze Zusammenfassung, max 3 Wörter, mit Unterstrichen statt Leerzeichen"
    )

def clean_filename(name):
    """Entfernt ungültige Zeichen für Dateinamen."""
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")

def process_pdf(file_path):
    """
    Hauptfunktion: OCR -> KI-Analyse -> Umbenennen & Verschieben
    """
    print(f"\n--- Starte Verarbeitung: {file_path.name} ---")
    
    try:
        # 1. OCR Schritt (Nutzt deine Funktion mit Poppler/Tesseract)
        ocr_text = perform_ocr_on_pdf(file_path)
        
        if not ocr_text or len(ocr_text.strip()) < 10:
            print(f"⚠️ Warnung: Kein Text per OCR erkannt für {file_path.name}")
            # Fallback, damit das Skript nicht abbricht
            ocr_text = "Dokument ohne erkennbaren Textinhalt"

        # 2. KI-Analyse mit Gemini
        model = genai.GenerativeModel('models/gemini-2.5-flash') # 'models/' Prefix für Stabilität
        
        prompt = f"""
        Analysiere diesen Text und extrahiere Metadaten für die Dateibenennung.
        Antworte NUR im JSON-Format wie folgt:
        {{
            "datum": "YYYY-MM-DD",
            "absender": "Name",
            "klassifizierung": "Typ",
            "summary": "Stichwort_Stichwort"
        }}
        Falls kein Datum gefunden wird, nutze '0000-00-00'.
        Text: {ocr_text[:4000]}
        """

        response = model.generate_content(prompt)
        
        # 3. JSON säubern und validieren
        # Entfernt mögliche Markdown-Formatierung der KI (```json ... ```)
        raw_json = response.text.replace("```json", "").replace("```", "").strip()
        data_dict = json.loads(raw_json)
        
        # In Pydantic Model laden zur Sicherheit
        doc_info = DocumentInfo(**data_dict)

        # 4. Neuen Dateinamen generieren
        clean_absender = clean_filename(doc_info.absender)
        clean_klass = clean_filename(doc_info.klassifizierung)
        clean_summ = clean_filename(doc_info.summary)
        
        new_name = f"{doc_info.datum}_{clean_absender}_{clean_klass}_{clean_summ}.pdf"
        target_path = OUTPUT_DIR / new_name

        # 5. Kollisionsprüfung (falls Datei schon existiert)
        counter = 1
        original_stem = target_path.stem
        while target_path.exists():
            target_path = OUTPUT_DIR / f"{original_stem}_{counter}.pdf"
            counter += 1

        # 6. Verschieben (shutil.move löst das WinError 17 Problem zwischen NAS und C:)
        print(f"Verschiebe nach: {target_path}")
        shutil.move(str(file_path), str(target_path))
        
        print(f"✅ Erfolgreich archiviert: {new_name}")

    except Exception as e:
        print(f"❌ Schwerer Fehler bei {file_path.name}: {e}")
        # Optional: Verschiebe Datei in einen "Fehler"-Ordner, damit der Loop nicht stoppt
        
        
# Pfad zum bin-Ordner von Poppler
POPPLER_PATH = r"C:\Programme\poppler-25.12.0\Library\bin" 
# Pfad zu tesseract.exe
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def perform_ocr_on_pdf(pdf_path):
    print(f"Konvertiere PDF zu Bildern: {pdf_path.name}")
    
    try:
        # 1. PDF-Seiten in Bilder umwandeln
        pages = convert_from_path(pdf_path, poppler_path=POPPLER_PATH)
        
        full_text = ""
        
        # 2. Jede Seite mit Tesseract auslesen
        for i, page in enumerate(pages):
            print(f"Scanne Seite {i+1}...")
            # 'deu' für Deutsch, 'eng' für Englisch
            text = pytesseract.image_to_string(page, lang="deu+eng")
            full_text += text + "\n"
            
        return full_text
        
    except Exception as e:
        print(f"Fehler bei der OCR-Verarbeitung: {e}")
        return None


def main():
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir()

    files = list(INPUT_DIR.glob("*.pdf"))
    if not files:
        print("Keine PDFs im Eingangsordner gefunden.")
        return

    for pdf_file in files:
        process_pdf(pdf_file)
        

if __name__ == "__main__":
    main()
    