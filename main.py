import atexit
import json
import logging
import re
import shutil
import socket
import tempfile
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
LOG_FILE = BASE_DIR / "server.log"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_MESSAGE_LEN = 5000
CHUNK_SIZE = 1024 * 1024
PORT = 8000

# Uploads are temporary: they live in a throwaway temp dir that is removed on
# exit. The log file (server.log) is the only thing kept on disk, on purpose.
UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="fastlan_"))
atexit.register(shutil.rmtree, UPLOAD_DIR, ignore_errors=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")],
)
log = logging.getLogger("fastlan")

app = FastAPI(title="FastLAN")


class ConnectionManager:
    def __init__(self):
        self.active: dict[WebSocket, int] = {}  # socket -> node number

    async def connect(self, ws: WebSocket, node: int):
        await ws.accept()
        self.active[ws] = node
        log.info("Client connected: %s (total %d)", ws.client.host, len(self.active))

    def disconnect(self, ws: WebSocket):
        if self.active.pop(ws, None) is not None:
            log.info("Client disconnected: %s (total %d)", ws.client.host, len(self.active))

    def online(self) -> list[int]:
        return sorted(set(self.active.values()))

    async def send(self, sockets: list[WebSocket], data: dict):
        for ws in sockets:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(ws)

    async def broadcast(self, data: dict):
        await self.send(list(self.active), data)

    async def broadcast_users(self):
        await self.broadcast({"type": "users", "nodes": self.online()})

    async def send_to_nodes(self, nodes: set[int], data: dict):
        """Deliver to every socket belonging to the given nodes."""
        await self.send([ws for ws, n in self.active.items() if n in nodes], data)


manager = ConnectionManager()

# Anonymous "node" numbers, assigned per client IP in order of first contact.
nodes: dict[str, int] = {}


def node_for(ip: str) -> int:
    return nodes.setdefault(ip, len(nodes) + 1)


def sanitize_filename(name: str) -> str:
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r"[^\w.\- ]", "_", name).strip(". ")
    return name[:150] or "file"


@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    if request.url.path == "/upload":
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_FILE_SIZE + 1024 * 100:
            log.warning("Rejected oversized upload from %s (%s bytes)", request.client.host, length)
            return JSONResponse({"detail": "File too large (max 100MB)"}, status_code=413)
    return await call_next(request)


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    node = node_for(ws.client.host)
    await manager.connect(ws, node)
    try:
        await ws.send_json({"type": "hello", "node": node})
        await manager.broadcast_users()
        while True:
            try:
                msg = json.loads(await ws.receive_text())
                text = str(msg.get("text", "")).strip()[:MAX_MESSAGE_LEN]
            except (ValueError, AttributeError):
                continue
            if not text:
                continue
            if msg.get("type") == "dm":
                to = msg.get("to")
                if not isinstance(to, int) or to == node:
                    await ws.send_json({"type": "error", "text": "Invalid recipient"})
                elif to not in manager.online():
                    await ws.send_json({"type": "error", "text": f"NODE {to:02d} is not online"})
                else:
                    # private: log metadata only, never the content
                    log.info("Private message from node %d to node %d", node, to)
                    await manager.send_to_nodes(
                        {node, to}, {"type": "dm", "from": node, "to": to, "text": text, "time": time.time()}
                    )
            else:
                log.info("Message from %s: %s", ws.client.host, text)
                await manager.broadcast({"type": "message", "node": node, "text": text, "time": time.time()})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)
        await manager.broadcast_users()


@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    client = request.client.host
    safe = sanitize_filename(file.filename or "file")
    stored = f"{int(time.time())}_{uuid.uuid4().hex[:6]}_{safe}"
    dest = UPLOAD_DIR / stored
    size = 0
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(413, "File too large (max 100MB)")
                out.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        log.warning("Upload from %s exceeded size limit: %s", client, safe)
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        log.exception("Upload failed from %s: %s", client, safe)
        raise HTTPException(500, "Upload failed")
    log.info("File uploaded by %s: %s (%d bytes) -> %s", client, safe, size, stored)
    await manager.broadcast(
        {"type": "file", "node": node_for(client), "name": safe, "url": f"/files/{stored}", "size": size, "time": time.time()}
    )
    return {"ok": True, "url": f"/files/{stored}"}


@app.get("/files/{stored}")
async def download(stored: str, request: Request):
    path = (UPLOAD_DIR / stored).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "Not found")
    log.info("File downloaded by %s: %s", request.client.host, stored)
    # strip the "timestamp_hash_" prefix for the saved name
    return FileResponse(path, filename=stored.split("_", 2)[-1])


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    print("\n  FastLAN is running. Open from any device on your network:")
    print(f"    http://{get_local_ip()}:{PORT}\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
