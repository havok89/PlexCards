import uvicorn
from backend.config import HOST, PORT

if __name__ == "__main__":
    print(f"Starting PlexCards server on http://{HOST}:{PORT}")
    uvicorn.run("backend.app:app", host=HOST, port=PORT, reload=False)
