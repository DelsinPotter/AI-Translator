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
console.log(f"frontendurl= {FRONTEND_URL}")
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
        temp_audio = tempfile.NamedTemporaryFile(delete=True, suffix=".mp3")
        tts.save(temp_audio.name)

        # Encrypt Audio Data
        with open(temp_audio.name, "rb") as file:
            encrypted_data = cipher.encrypt(file.read())
        
        return JSONResponse({
            "original_text": text,
            "translated_text": translated_text,
            "audio_data": encrypted_data.decode()  # Send encrypted data directly
        })
    except Exception as e:
        logging.error(f"Error during translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/audio/play")
async def serve_audio(encrypted_audio: str):
    try:
        decrypted_data = cipher.decrypt(encrypted_audio.encode())
        return StreamingResponse(
            iter([decrypted_data]), media_type="audio/mp3"
        )
    except Exception as e:
        logging.error(f"Error decrypting audio: {e}")
        raise HTTPException(status_code=500, detail="Error decrypting audio")
