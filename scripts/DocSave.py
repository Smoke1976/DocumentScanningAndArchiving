import os
import shutil

def archive_document(pdf_path, metadata, target_folder):
    # Erstelle einen sauberen Dateinamen
    # Beispiel: 2023-12-01_Vodafone_Rechnung.pdf
    clean_sender = metadata['absender'].replace(" ", "_")
    new_name = f"{metadata['datum']}_{clean_sender}_{metadata['typ']}.pdf"
    
    dest_path = os.path.join(target_folder, new_name)
    
    # Datei verschieben
    shutil.move(pdf_path, dest_path)
    print(f"Archiviert: {new_name}")