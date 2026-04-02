import os
from scripts.DocSplitter import split_pdf_gemini_hybrid
from scripts.DocExtractor import extract_text_from_pdf, classify_and_extract
from scripts.DocSave import archive_document

def main():
    input_folder = "data/input"
    temp_folder = "data/temp_split" # Zwischenlager für die Einzelteile
    final_archive = "data/output"
    
    # Ordner erstellen, falls sie fehlen
    os.makedirs(temp_folder, exist_ok=True)
    os.makedirs(final_archive, exist_ok=True)

    # 1. Suche nach neuen Scans
    scans = [f for f in os.listdir(input_folder) if f.endswith(".pdf")]
    
    for scan in scans:
        print(f"--- Starte Verarbeitung für {scan} ---")
        full_path = os.path.join(input_folder, scan)
        
        # 2. In Einzeldokumente splitten
        split_pdf_gemini_hybrid(full_path, temp_folder)
        
        # 3. Jedes neue Dokument verarbeiten
        for split_doc in os.listdir(temp_folder):
            doc_path = os.path.join(temp_folder, split_doc)
            
            try:
                # Text extrahieren (inkl. OCR falls nötig)
                text = extract_text_from_pdf(doc_path)
                
                # KI-Analyse
                metadata = classify_and_extract(text)
                print(f"Erkannt: {metadata['typ']} von {metadata['absender']}")
                
                # Archivieren
                archive_document(doc_path, metadata, final_archive)
                
            except Exception as e:
                print(f"Fehler bei {split_doc}: {e}")

    print("--- Prozess abgeschlossen ---")

if __name__ == "__main__":
    main()