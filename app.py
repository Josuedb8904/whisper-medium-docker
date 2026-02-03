import os
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel
import tempfile
from typing import Optional
import time

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear app FastAPI
app = FastAPI(
    title="Whisper Medium API",
    description="API de transcripción de audio usando Whisper Medium",
    version="1.0.0"
)

# Configuración del modelo
MODEL_SIZE = os.getenv("WHISPER_MODEL", "medium")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "100")) * 1024 * 1024  # 100MB default

# Inicializar modelo
logger.info(f"Cargando modelo Whisper {MODEL_SIZE}...")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
logger.info("Modelo cargado exitosamente")

@app.get("/")
async def root():
    """Endpoint raíz - información básica de la API"""
    return {
        "message": "Whisper Medium API",
        "version": "1.0.0",
        "model": MODEL_SIZE,
        "device": DEVICE,
        "endpoints": {
            "/health": "Estado de salud del servicio",
            "/transcribe": "Transcribir audio (POST)",
            "/models": "Información del modelo"
        }
    }

@app.get("/health")
async def health_check():
    """Endpoint de health check para Dokploy"""
    return {
        "status": "healthy",
        "model": MODEL_SIZE,
        "device": DEVICE
    }

@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    task: Optional[str] = Form("transcribe")
):
    """
    Transcribir archivo de audio
    
    - **file**: Archivo de audio (MP3, WAV, M4A, etc.)
    - **language**: Código de idioma (opcional, ej: 'es', 'en')
    - **task**: 'transcribe' o 'translate' (default: transcribe)
    """
    
    # Validar tamaño del archivo
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo: {MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    # Validar formato
    allowed_formats = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm']
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Formatos permitidos: {', '.join(allowed_formats)}"
        )
    
    # Guardar archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        temp_file.write(contents)
        temp_path = temp_file.name
    
    try:
        logger.info(f"Transcribiendo archivo: {file.filename}")
        start_time = time.time()
        
        # Transcribir
        segments, info = model.transcribe(
            temp_path,
            language=language,
            task=task,
            vad_filter=True,  # Voice Activity Detection
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        # Procesar segmentos
        transcription_segments = []
        full_text = []
        
        for segment in segments:
            transcription_segments.append({
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip()
            })
            full_text.append(segment.text.strip())
        
        duration = time.time() - start_time
        
        logger.info(f"Transcripción completada en {duration:.2f}s")
        
        return JSONResponse(content={
            "success": True,
            "text": " ".join(full_text),
            "segments": transcription_segments,
            "language": info.language,
            "language_probability": round(info.language_probability, 2),
            "duration": round(info.duration, 2),
            "processing_time": round(duration, 2)
        })
        
    except Exception as e:
        logger.error(f"Error en transcripción: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al transcribir: {str(e)}")
        
    finally:
        # Limpiar archivo temporal
        if os.path.exists(temp_path):
            os.unlink(temp_path)

@app.get("/models")
async def get_model_info():
    """Información sobre el modelo actual"""
    return {
        "model_size": MODEL_SIZE,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "max_file_size_mb": MAX_FILE_SIZE / 1024 / 1024
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "9000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
