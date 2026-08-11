"""
FastAPI server for the CorAi HeartAI Copilot.

This is a standalone API that exposes the RAG-backed chatbot from
``rag_engine.py`` over HTTP. The main CorAi Flask app already has a
``/chat`` route that does the same thing via the existing blueprint; this
file is a separate, self-contained server you can run if you want a
dedicated Python service for the chatbot (e.g. behind a different reverse
proxy, or in a different process from the Flask app).

Run:
    pip install fastapi uvicorn pydantic
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag_engine import (
    configure,
    get_bot_response,
    get_bot_response_safe,
    is_configured,
    status,
)

log = logging.getLogger("corai.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

app = FastAPI(title="CorAi Chatbot Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    message: str


class StatusResponse(BaseModel):
    ready: bool
    detail: dict


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz", response_model=StatusResponse)
def readyz() -> StatusResponse:
    info = status()
    return StatusResponse(ready=is_configured(), detail=info)


@app.post("/api/chat")
async def chat_endpoint(request: QueryRequest) -> dict:
    msg = (request.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")
    try:
        reply = get_bot_response(msg)
    except RuntimeError as exc:
        # RAG deps missing or GOOGLE_API_KEY not set. Fall back to the safe
        # wrapper so the caller still gets a 200 with a clear message.
        log.warning("RAG not ready (%s); using safe fallback", exc)
        reply = get_bot_response_safe(msg)
    return {"reply": reply}


# When imported as a module, ``configure`` can be called from the embedding
# server / startup script. When run directly (``uvicorn main:app``), nothing
# extra needs to happen — the GOOGLE_API_KEY env var is read on first request.
