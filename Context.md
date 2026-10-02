# Project Context: FastAPI LAN Communication Server

## 1. Project Overview
A lightweight, high-performance **FastAPI server** written in Python that enables devices on the same Local Area Network (LAN) to text and share files instantly.

* **Anonymous & Stateless:** Purely shared, real-time message and file feed. No user authentication, login screens, or persistent database required.
* **Robust Logging:** Built-in Python logging tracks all server activities, client connections, messages, and file actions to both the terminal console and a log file.
* **Cross-Platform Compatibility:** Fully optimized for Google Chrome and Mozilla Firefox across desktop computers, laptops, and mobile devices (iOS/Android).

---

## 2. Recommended Tech Stack
* **Language & Runtime:** Python 3.10+
* **Framework & ASGI Server:** **FastAPI** paired with **Uvicorn** for lightning-fast async request handling.
* **Real-Time Communication:** FastAPI's native `WebSocket` support managed via a custom connection manager for instant broadcasting.
* **File Management:** FastAPI `UploadFile` and `python-multipart` for handling multipart form data. Files are stored locally in an `uploads/` directory and served via `StaticFiles`.
* **Logging System:** Python's built-in `logging` module configured with timestamps and formatting.
* **Frontend UI:** Single-file architecture (`index.html`) using modern responsive CSS (Flexbox/Grid) and Vanilla JavaScript.

---

## 3. Core Features & Architecture Requirements

### A. Real-Time Chat (WebSockets)
* **Connection Manager:** Tracks active WebSocket connections to broadcast incoming text messages and file notices to all connected clients instantly.
* **Live Feed:** An anonymous, sequential chat stream displaying messages cleanly.
* **Auto-Reconnect:** Frontend JavaScript logic to gracefully handle temporary network blips or mobile sleep states by attempting automatic WebSocket reconnections.

### B. File Sharing
* **Upload Interface:** Drag-and-drop zone alongside a standard mobile-friendly file picker.
* **Storage & Naming Strategy:** Server saves files to disk. To prevent filename collisions, prepend a timestamp or unique hash to uploaded filenames (e.g., `timestamp_filename.ext`).
* **Broadcast Link:** Once uploaded, the server broadcasts a clickable download link directly into the active chat stream.

### C. LAN Accessibility & Logging
* **Network Binding:** Must run via Uvicorn explicitly bound to `host="0.0.0.0"` to accept incoming connections from other devices on the LAN.
* **IP Discovery Helper:** On startup, automatically query local network interfaces and print clear access instructions (e.g., `http://192.168.1.50:8000`) to the console.
* **Structured Logging:** Log connection events, text transmissions, and file transfers using standard formatting (`%(asctime)s - %(levelname)s - %(message)s`).

### D. Security & Edge Cases (Lightweight Guardrails)
* **File Size Limits:** Implement a reasonable maximum file size restriction (e.g., 50MB or 100MB) via FastAPI middleware or chunked verification to prevent memory exhaustion.
* **Path Traversal Protection:** Ensure filenames are sanitized using `pathlib` or `werkzeug.utils.secure_filename` before saving to disk.

---

## 4. Suggested Directory Structure
```text
lan-server/
│
├── main.py             # FastAPI backend, WebSocket manager, file routes, logging
├── requirements.txt    # Dependencies (fastapi, uvicorn, python-multipart)
├── static/
│   └── index.html      # Responsive frontend UI (HTML, CSS, Vanilla JS)
└── uploads/            # Local directory where shared files are stored