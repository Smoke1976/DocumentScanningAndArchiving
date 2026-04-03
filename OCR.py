import ocrmypdf

def apply_ocr_to_pdf(input_path, output_path=None):
    """
    Führt OCR auf einer PDF aus. Wenn kein output_path angegeben ist, 
    wird die Originaldatei überschrieben.
    """
    if output_path is None:
        output_path = input_path

    print(f"Starte OCR für {input_path}...")
    
    try:
        # deskew: Richtet schiefe Scans gerade
        # clean: Entfernt Rauschen aus dem Scan
        # language: 'deu' für Deutsch, 'eng' für Englisch
        ocrmypdf.ocr(input_path, output_path, 
                    language=["deu", "eng"], 
                    deskew=True, 
                    clean=True,
                    skip_text=True) # Überspringt Seiten, die bereits Text haben
        
        print(f"OCR erfolgreich abgeschlossen: {output_path}")
        return True
    except Exception as e:
        print(f"OCR Fehler: {e}")
        return False