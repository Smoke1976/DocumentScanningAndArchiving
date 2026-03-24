import os
import re
import shutil


def sanitize_filename(name):
    """Erlaubt nur sichere Zeichen und ersetzt Leerzeichen durch Unterstriche."""
    # Entferne Pfad-Trennzeichen und nicht erlaubte Zeichen
    name = os.path.basename(name)
    name = name.replace(' ', '_')
    # Zulässige Zeichen: alphanumerisch, -, _, .
    name = re.sub(r'[^a-zA-Z0-9_\-.]', '', name)
    # Keine Punkte am Anfang
    name = name.lstrip('.')
    return name or 'unnamed'


def archive_document(pdf_path, metadata, target_folder):
    # Erstelle einen sauberen Dateinamen
    # Beispiel: 2023-12-01_Vodafone_Rechnung.pdf
    clean_sender = sanitize_filename(metadata.get('absender', 'unbekannt'))
    clean_typ = sanitize_filename(metadata.get('typ', 'Sonstiges'))
    clean_datum = sanitize_filename(metadata.get('datum', 'kein_datum'))
    new_name = f"{clean_datum}_{clean_sender}_{clean_typ}.pdf"

    dest_path = os.path.join(target_folder, new_name)

    # Datei verschieben
    shutil.move(pdf_path, dest_path)
    print(f"Archiviert: {new_name}")