#!/usr/bin/env python3
"""
Main Entrypoint for Codebase & IT Infrastructure Incident Assistant
Supports running the FastAPI server and triage console.
"""

import uvicorn

if __name__ == "__main__":
    print("[*] Starting Incident Assistant Server on http://127.0.0.1:8000 ...")
    uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=False)
