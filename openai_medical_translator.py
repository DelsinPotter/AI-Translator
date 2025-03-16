from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse, FileResponse
from gtts import gTTS
from cryptography.fernet import Fernet
import tempfile
import logging
import google.generativeai as genai
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Adjust based on frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Configure Logging
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Encryption Key for Audio
encryption_key = Fernet.generate_key()
cipher = Fernet(encryption_key)

# Gemini API Key
GEMINI_API_KEY = "AIzaSyBwBLTL5dmnfo0ge-fgjlYU01OOWAQvPdE"
genai.configure(api_key=GEMINI_API_KEY)

@app.post("/translate/")
async def translate_and_speak(
    text: str = Form(...),
    input_lang_code: str = Form(...),
    output_lang_code: str = Form(...)
):
    try:
        # Translate Text using Free Gemini Model
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = f"Translate the following text from {input_lang_code} to {output_lang_code} and do not add english transliteration: {text} "
        response = model.generate_content(prompt)
        translated_text = response.text.strip()

        # Generate Audio
        tts = gTTS(translated_text, lang=output_lang_code)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            tts.save(temp_audio.name)

            # Encrypt the file
            with open(temp_audio.name, "rb") as file:
                encrypted_data = cipher.encrypt(file.read())
            with open(temp_audio.name, "wb") as file:
                file.write(encrypted_data)
        print(f"original_text {text},translated_text: {translated_text},  audio_file: {temp_audio.name} ")
        audio_filename = os.path.basename(temp_audio.name)  # Extract only the filename

        return JSONResponse({
            "original_text": text,
            "translated_text": translated_text,
            "audio_file": audio_filename  # Return only filename, not full path
        })

    
    except Exception as e:
        logging.error(f"Error during translation: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    try:
        # Decrypt and serve audio file
        decrypted_path = f"decrypted_{filename}"
        file_path = os.path.join(tempfile.gettempdir(), filename)  # Locate the temp file
        with open(file_path, "rb") as file:
            encrypted_data = file.read()
        with open(decrypted_path, "wb") as file:
            file.write(cipher.decrypt(encrypted_data))
        print(f"decrypted_path {decrypted_path}")
        return FileResponse(decrypted_path, media_type="audio/mp3")
    except Exception as e:
        logging.error(f"Error decrypting audio: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
