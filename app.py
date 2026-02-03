from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
import whisper
import tempfile
import os
from typing import Optional
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Whisper Audio Transcription API",
    description="API REST para transcripción de audio usando Whisper Medium",
    version="1.0.0"
)

# Inicializar modelo Whisper Medium (se carga al iniciar)
logger.info("Cargando modelo Whisper Medium...")
model = whisper.load_model("medium")
logger.info("Modelo cargado exitosamente!")

# Configuración
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".mpeg", ".mpga", ".webm", ".ogg", ".flac"}


@app.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "message": "Whisper Audio Transcription API",
        "version": "1.0.0",
        "model": "medium",
        "endpoints": {
            "health": "/health",
            "transcribe": "/transcribe (POST)",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check del servicio"""
    return {
        "status": "healthy",
        "model": "medium",
        "device": "cpu"
    }


@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    task: Optional[str] = Form("transcribe")
):
    """
    Transcribir un archivo de audio
    
    Parámetros:
    - file: Archivo de audio (MP3, WAV, M4A, etc.)
    - language: Código de idioma (opcional, ej: 'es', 'en'). Si no se especifica, se detecta automáticamente
    - task: 'transcribe' o 'translate' (traducir a inglés)
    
    Retorna:
    - text: Transcripción completa
    - segments: Lista de segmentos con timestamps
    - language: Idioma detectado
    """
    
    # Validar extensión del archivo
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de archivo no soportado. Formatos permitidos: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Leer el archivo
    try:
        contents = await file.read()
        file_size = len(contents)
        
        # Validar tamaño
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Archivo demasiado grande. Tamaño máximo: {MAX_FILE_SIZE / (1024*1024):.0f}MB"
            )
        
        # Guardar temporalmente el archivo
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(contents)
            tmp_file_path = tmp_file.name
        
        logger.info(f"Procesando archivo: {file.filename} ({file_size / 1024:.2f} KB)")
        
        # Transcribir con Whisper
        result = model.transcribe(
            tmp_file_path,
            language=language,
            task=task
        )
        
        # Procesar segmentos
        segments_list = []
        for segment in result.get("segments", []):
            segment_dict = {
                "start": round(segment["start"], 2),
                "end": round(segment["end"], 2),
                "text": segment["text"].strip()
            }
            segments_list.append(segment_dict)
        
        # Limpiar archivo temporal
        os.unlink(tmp_file_path)
        
        logger.info(f"Transcripción completada. Idioma: {result.get('language', 'unknown')}")
        
        return JSONResponse(content={
            "success": True,
            "text": result["text"].strip(),
            "segments": segments_list,
            "language": result.get("language", "unknown"),
            "file_name": file.filename
        })
        
    except Exception as e:
        # Limpiar archivo temporal en caso de error
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        
        logger.error(f"Error al procesar audio: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar el audio: {str(e)}"
        )


@app.get("/models")
async def get_models():
    """Información sobre el modelo cargado"""
    return {
        "current_model": "medium",
        "device": "cpu",
        "supported_languages": [
            "es", "en", "fr", "de", "it", "pt", "nl", "pl", "ru", "ja", 
            "ko", "zh", "ar", "tr", "vi", "th", "sv", "da", "no", "fi"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
