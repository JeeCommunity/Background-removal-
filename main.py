import os
import io
import time
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from rembg import remove, new_session

app = FastAPI(
    title="AI Background Removal API & Web UI",
    description="High-performance ONNX background removal service using rembg with ISNet and U2Net models.",
    version="3.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pure lazy-load sessions for instant container startup and zero health-check timeout / restarts
sessions = {}

def get_session(model_name: str):
    valid_models = ["u2netp", "isnet-general-use", "u2net", "silueta"]
    if model_name not in valid_models:
        model_name = "u2netp"
    
    if model_name not in sessions:
        try:
            print(f"Loading model session on-demand: {model_name}...")
            sessions[model_name] = new_session(model_name)
            print(f"Successfully loaded model session: {model_name}")
        except Exception as e:
            print(f"Failed to load session {model_name}: {e}")
            if model_name != "u2netp":
                return get_session("u2netp")
            raise e
    return sessions.get(model_name)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "loaded_models": list(sessions.keys()),
        "default_model": "u2netp",
        "engine": "ONNX Runtime (rembg)",
        "local": True
    }

@app.get("/models")
def get_models():
    return {
        "models": [
            {
                "id": "u2netp",
                "name": "U2Net Light (Fastest)",
                "description": "Ultra-fast lightweight model for instant processing and zero-download deployment (~4.7 MB)",
                "size": "~4.7 MB",
                "loaded": "u2netp" in sessions
            },
            {
                "id": "isnet-general-use",
                "name": "ISNet General (Best Quality)",
                "description": "State-of-the-art general purpose background removal with incredible hair and edge details (~175 MB)",
                "size": "~175 MB",
                "loaded": "isnet-general-use" in sessions
            },
            {
                "id": "u2net",
                "name": "U2Net Standard",
                "description": "Robust general-purpose background removal for objects and portraits (~175 MB)",
                "size": "~175 MB",
                "loaded": "u2net" in sessions
            },
            {
                "id": "silueta",
                "name": "Silueta",
                "description": "Lightweight silhouette extraction model (~45 MB)",
                "size": "~45 MB",
                "loaded": "silueta" in sessions
            }
        ],
        "active_model": "u2netp"
    }

@app.post("/remove-background")
async def remove_background(
    file: UploadFile = File(...),
    model: str = Form("u2netp")
):
    if model not in ["isnet-general-use", "u2net", "silueta", "u2netp"]:
        model = "isnet-general-use"
    
    try:
        start_time = time.time()
        image_bytes = await file.read()
        try:
            input_image = Image.open(io.BytesIO(image_bytes))
            input_image.verify()
            input_image = Image.open(io.BytesIO(image_bytes))
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid image file format."
            )
        
        session = get_session(model)
        output_image = remove(input_image, session=session)
        
        elapsed = time.time() - start_time
        
        output_buffer = io.BytesIO()
        output_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        
        response = Response(content=output_buffer.getvalue(), media_type="image/png")
        response.headers["X-Processing-Time"] = f"{elapsed:.3f}s"
        response.headers["X-Model-Used"] = model
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Background removal failed: {str(e)}")

# Serve React frontend static files if dist exists
if os.path.exists("dist"):
    if os.path.exists("dist/assets"):
        app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

    @app.get("/")
    def serve_root():
        return FileResponse("dist/index.html")

    @app.get("/{path:path}")
    def serve_spa(path: str):
        if path.startswith("api/") or path in ["health", "models", "remove-background"]:
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = os.path.join("dist", path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse("dist/index.html")
else:
    @app.get("/")
    def root():
        return {
            "service": "AI Background Removal API & Web UI",
            "status": "online",
            "endpoints": {
                "health": "/health",
                "models": "/models",
                "remove_background": "/remove-background",
                "docs": "/docs"
            }
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
