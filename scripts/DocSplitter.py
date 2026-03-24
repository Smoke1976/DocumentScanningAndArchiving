import os
import ollama
from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter
import io

def split_pdf_locally(input_pdf_path, output_folder):
    print(f"Verarbeite: {input_pdf_path}...")
    images = convert_from_path(input_pdf_path)
    reader = PdfReader(input_pdf_path)
    
    writer = PdfWriter()
    doc_count = 1

    for i, image in enumerate(images):
        # Bild in Bytes umwandeln für Ollama
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        # Lokale KI (Llava) fragen
        response = ollama.generate(
            model='llava',
            prompt="Ist dies die erste Seite eines neuen Dokuments? Antworte nur mit JA oder NEIN.",
            images=[img_bytes]
        )

        is_new_doc = "JA" in response['response'].upper()

        if is_new_doc and i > 0:
            save_pdf(writer, output_folder, doc_count)
            writer = PdfWriter()
            doc_count += 1
        
        writer.add_page(reader.pages[i])

    save_pdf(writer, output_folder, doc_count)

def save_pdf(writer, folder, count):
    path = os.path.join(folder, f"split_doc_{count}.pdf")
    with open(path, "wb") as f:
        writer.write(f)
    print(f"Gespeichert: {path}")

# split_pdf_locally("data/input/mein_scan.pdf", "data/output/")
