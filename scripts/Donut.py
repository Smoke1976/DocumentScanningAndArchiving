import torch
from transformers import DonutProcessor, VisionEncoderDecoderModel
from PIL import Image
from pdf2image import convert_from_path
import io

# 1. Modell und Processor laden (beim ersten Mal werden ca. 800MB geladen)
processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base-finetuned-rvlcdip")
model = VisionEncoderDecoderModel.from_pretrained("naver-clova-ix/donut-base-finetuned-rvlcdip")

# Falls du eine GPU hättest, würde hier .to("cuda") stehen, bei dir bleibt es CPU
device = "cpu"
model.to(device)

def classify_with_donut(pdf_path):
    # PDF-Seite 1 in Bild umwandeln
    images = convert_from_path(pdf_path, first_page=1, last_page=1)
    image = images[0].convert("RGB")

    # Bild für das Modell vorbereiten
    pixel_values = processor(image, return_tensors="pt").pixel_values

    # Task-spezifische Tokens vorbereiten
    task_prompt = "<s_rvlcdip>" # Start-Token für Klassifizierung
    decoder_input_ids = processor.tokenizer(task_prompt, add_special_tokens=False, return_tensors="pt").input_ids

    # Generierung (Vorhersage)
    outputs = model.generate(
        pixel_values.to(device),
        decoder_input_ids=decoder_input_ids.to(device),
        max_length=model.config.decoder.max_position_embeddings,
        pad_token_id=processor.tokenizer.pad_token_id,
        eos_token_id=processor.tokenizer.eos_token_id,
        use_cache=True,
        bad_words_ids=[[processor.tokenizer.unk_token_id]],
        return_dict_in_generate=True,
    )

    # Ergebnis dekodieren
    sequence = processor.batch_decode(outputs.sequences)[0]
    sequence = sequence.replace(processor.tokenizer.eos_token, "").replace(processor.tokenizer.pad_token, "")
    # Extrahiere das Label aus den speziellen Tags
    label = sequence.split("<s_rvlcdip>")[1].strip()
    return label

# Testlauf
print(classify_with_donut("data/input/08_Elektro.pdf"))