from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
from gtts import gTTS
import openai
from cryptography.fernet import Fernet
import tempfile
import os
import logging

app = FastAPI()

# Configure Logging
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load Encryption Key from Environment Variable (or Generate if Missing)
encryption_key = os.getenv("AUDIO_ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(encryption_key.encode())

# Load OpenAI API Key
openai_api_key = os.getenv("OPENAI_API_KEY")

def translate_text(text, source_lang, target_lang):
    prompt = f"Translate the following text from {source_lang} to {target_lang}: {text}"
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": "You are a professional translator."},
                  {"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"].strip()

# Language Mapping
LANGUAGE_MAPPING = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "zh": "Chinese", "ar": "Arabic", "hi": "Hindi", "it": "Italian",
    "pt": "Portuguese", "ru": "Russian", "ja": "Japanese", "ko": "Korean",
    "tr": "Turkish"
}

@app.post("/translate/")
async def translate_and_speak(
    text: str = Form(...),
    input_lang_code: str = Form(...),
    output_lang_code: str = Form(...)
):
    try:
        # Translate Text using OpenAI GPT
        translated_text = translate_text(text, LANGUAGE_MAPPING.get(input_lang_code, input_lang_code), LANGUAGE_MAPPING.get(output_lang_code, output_lang_code))

        # Generate Audio
        tts = gTTS(translated_text, lang=output_lang_code)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            tts.save(temp_audio.name)
            audio_filename = temp_audio.name

        # Encrypt Audio File
        with open(audio_filename, "rb") as file:
            encrypted_data = cipher.encrypt(file.read())
        encrypted_filename = f"encrypted_{os.path.basename(audio_filename)}"
        with open(encrypted_filename, "wb") as file:
            file.write(encrypted_data)

        # Cleanup Original Audio File
        os.remove(audio_filename)

        return JSONResponse({
            "original_text": text,
            "translated_text": translated_text,
            "audio_file": encrypted_filename
        })

    except Exception as e:
        logging.error(f"Error during translation: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    try:
        encrypted_path = filename
        decrypted_path = f"decrypted_{filename}"  # Temporary decrypted file

        # Decrypt Audio File
        with open(encrypted_path, "rb") as file:
            encrypted_data = file.read()
        with open(decrypted_path, "wb") as file:
            file.write(cipher.decrypt(encrypted_data))

        # Serve Audio & Schedule Deletion
        response = FileResponse(decrypted_path, media_type="audio/mp3")
        os.remove(decrypted_path)
        return response
    except Exception as e:
        logging.error(f"Error decrypting audio: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
