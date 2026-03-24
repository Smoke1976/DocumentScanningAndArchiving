import os
import ollama
import re
from pypdf import PdfReader, PdfWriter

def is_new_doc_qwen(text_chunk):
    """Prüft mit Qwen2-0.5b, ob eine neue Seite beginnt."""
    # Sehr kurzer, präziser Prompt für kleine Modelle
    prompt = f"""Task: Is this the first page of a NEW document? 
    Text: {text_chunk[:500]}
    Answer only 'YES' or 'NO'."""

    try:
        response = ollama.generate(
            model='qwen2:0.5b', 
            prompt=prompt,
            options={
                "num_predict": 5, 
                "temperature": 0,
                "num_thread": 4 # Nutzt 4 CPU-Kerne auf deinem Kali
            }
        )
        result = response['response'].strip().upper()
        return "YES" in result
    except Exception as e:
        print(f"Fehler bei Qwen-Abfrage: {e}")
        return False

def split_pdf_qwen_hybrid(input_pdf_path, output_folder):
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    doc_count = 1
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        
        # 1. Schneller Regex-Vorfilter (spart CPU-Zeit)
        if "seite 2" in text.lower() or "page 2" in text.lower():
            is_new = False
        elif "seite 1" in text.lower() or "page 1" in text.lower():
            is_new = True
        else:
            # 2. Nur wenn Regex nicht hilft, fragen wir Qwen
            is_new = is_new_doc_qwen(text)
        
        if is_new and i > 0:
            save_pdf(writer, output_folder, doc_count)
            writer = PdfWriter()
            doc_count += 1
            
        writer.add_page(page)

    save_pdf(writer, output_folder, doc_count)

def save_pdf(writer, folder, count):
    path = os.path.join(folder, f"doc_{count}.pdf")
    with open(path, "wb") as f:
        writer.write(f)