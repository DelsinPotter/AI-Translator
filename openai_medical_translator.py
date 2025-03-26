from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from gtts import gTTS
from cryptography.fernet import Fernet
import tempfile
import logging
import google.generativeai as genai
import os
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL")

if not GEMINI_API_KEY or not ENCRYPTION_KEY:
    raise ValueError("Missing required environment variables")

# Configure API Key
genai.configure(api_key=GEMINI_API_KEY)

# Encryption Setup
cipher = Fernet(ENCRYPTION_KEY.encode())

# Configure Logging
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = FastAPI()
# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/translate/")
async def translate_and_speak(
    text: str = Form(...),
    input_lang_code: str = Form(...),
    output_lang_code: str = Form(...)
):
    try:
        # Translate Text using Free Gemini Model
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
                f"You are a medical translation AI specializing in healthcare communication. "
                f"Translate the following text from {input_lang_code} to {output_lang_code} with medical accuracy. "
                f"Ensure correct usage of medical terminology and avoid adding English transliteration. "
                f"Maintain the original meaning without altering critical medical details:\n\n"
                f"Text: {text}"
                )
        response = model.generate_content(prompt)
        translated_text = response.text.strip() if response.text else ""
        
        if not translated_text:
            raise HTTPException(status_code=500, detail="Translation failed.")
        
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    try:
        # Locate the encrypted audio file
        file_path = os.path.join(tempfile.gettempdir(), filename)

        # Decrypt the audio file
        decrypted_path = os.path.join(tempfile.gettempdir(), f"decrypted_{filename}")
        with open(file_path, "rb") as file:
            encrypted_data = file.read()
        
        with open(decrypted_path, "wb") as file:
            file.write(cipher.decrypt(encrypted_data))  # Decrypt before sending
        
        print(f"Decrypted audio file path: {decrypted_path}")

        return FileResponse(decrypted_path, media_type="audio/mp3")

    except Exception as e:
        logging.error(f"Error decrypting audio: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

