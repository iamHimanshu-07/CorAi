"""
RAG engine for the CorAi HeartAI Copilot.

Builds a small FAISS index from a built-in knowledge base, embeds with a local
HuggingFace MiniLM model, and answers user questions via Google Gemini.

The knowledge base text below is CorAi-specific (this is the Heart-Disease
Prediction System, not Hearly AI). To re-skin for a different product, replace
the ``corai_kb_content`` string — the same chunking, embedding, and Gemini
plumbing will pick it up automatically.

Requirements (install yourself before running):
    pip install langchain langchain-community langchain-google-genai \
                faiss-cpu sentence-transformers google-generativeai

Configuration:
    Set ``GOOGLE_API_KEY`` in the environment, or pass ``google_api_key=...``
    to ``configure(...)``.

    The on-disk FAISS index is cached at ``./.rag_cache/corai_index`` so we
    don't re-embed on every cold start. Delete that directory to rebuild.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Lazy import shims — module loads even if RAG deps aren't installed yet so
# the rest of the Flask app keeps working. The chatbot blueprint falls back to
# the OpenAI path if ``is_configured()`` is False.
#
# IMPORTANT: we keep ``_RAG_DEPS_OK`` as ``None`` (unknown) until the first
# chat request asks. Importing langchain + faiss-cpu + sentence-transformers
# here would eagerly load PyTorch, which OOM-kills Render's 512 MB free-tier
# workers before gunicorn ever binds $PORT.
_RAG_DEPS_OK: bool | None = None
_import_error: str | None = None
_deps_lock = threading.Lock()


def _probe_deps() -> bool:
    """One-shot probe of RAG dependencies. Safe to call multiple times."""
    global _RAG_DEPS_OK, _import_error
    if _RAG_DEPS_OK is not None:
        return _RAG_DEPS_OK
    with _deps_lock:
        if _RAG_DEPS_OK is not None:
            return _RAG_DEPS_OK
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: F401
            from langchain_community.vectorstores import FAISS  # noqa: F401
            from langchain_community.embeddings import HuggingFaceEmbeddings  # noqa: F401
            from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: F401
            from langchain_classic.chains.retrieval import create_retrieval_chain  # noqa: F401
            from langchain_classic.chains.combine_documents.stuff import create_stuff_documents_chain  # noqa: F401
            from langchain_core.prompts import ChatPromptTemplate  # noqa: F401
            _RAG_DEPS_OK = True
        except Exception as exc:  # noqa: BLE001
            _RAG_DEPS_OK = False
            _import_error = repr(exc)
    return _RAG_DEPS_OK


# --------------------------------------------------------------------------- #
# Knowledge base
# --------------------------------------------------------------------------- #

# CorAi product copy. Keep it short and factual — this is the source of truth
# the assistant will quote back to users. Re-skin the variable name + content
# to swap products.
corai_kb_content = """
CorAi (CorAi) is an open-source clinical decision
support tool that estimates cardiovascular risk from 11 routine measurements:
age, resting blood pressure, cholesterol, fasting blood sugar, max heart rate,
ST depression (Oldpeak), sex, chest pain type, resting ECG, exercise-induced
angina, and ST slope.

Risk bands
----------
CorAi returns three risk bands based on the predicted probability:
- Low: probability <= 30 percent.
- Moderate: probability between 30 and 60 percent (inclusive of 30, exclusive of 60).
- High: probability > 60 percent.
The thresholds live in ``app/predict.py`` and ``app/services/pdf_report.py``.

What it does
------------
The user enters the 11 features in the web form, the model returns a
probability (0 to 100 percent) and a Low, Moderate, or High risk band.
Every prediction is logged in an audit table with the input features, the
model version, and the user that triggered it. Doctors and admins can
download a PDF analysis report with a risk gauge and feature breakdown.

Models and accuracy
-------------------
CorAi trains four classifiers on the UCI heart disease dataset (918 rows,
11 features): logistic regression, random forest, XGBoost, and LightGBM.
Each model is isotonic-calibrated with 5-fold CV. The model with the highest
mean cross-validated ROC-AUC is selected. SHAP per-prediction feature
contributions are available on the result page.

Roles
-----
- Doctor: full access to the patient registry, can run predictions on behalf
  of any patient, download PDF reports, and access the metrics page.
- Patient: can register themselves, run predictions on their own inputs,
  download PDF reports, and view the doctor map.
- Admin: everything a doctor can do plus user management and the full audit
  log.

Features
--------
- Manual prediction form (11 features).
- PDF medical report upload: extract patient metrics from a PDF and run a
  prediction automatically.
- Doctor map: area-wise cardiologist recommendations via OpenStreetMap.
- HeartAI Copilot: this chatbot, available as a floating widget on every
  authenticated page.
- Bootstrap doctor account: username "doctor", default password "corai2026"
  (change immediately in production).

Pricing and license
-------------------
CorAi is MIT-licensed and free to study. It is educational software, not a
clinical diagnosis tool. See MODEL_CARD.md for intended use and limitations.

Support
-------
Open an issue on the GitHub repository or contact the maintainer, Himanshu
Singh Yadav, via the project README.
"""


# --------------------------------------------------------------------------- #
# Module-level state (lazy singleton)
# --------------------------------------------------------------------------- #

_lock = threading.Lock()
_rag_chain: Any | None = None
_embed_model_name: str = os.getenv("CorAi_EMBED_MODEL", "all-MiniLM-L6-v2")
_gemini_model_name: str = os.getenv("CorAi_GEMINI_MODEL", "gemini-flash-latest")
_index_dir: Path = Path(os.getenv("CorAi_RAG_INDEX", "./.rag_cache/corai_index"))
# Pin the HuggingFace cache to a directory we control. The default cache
# path on Windows is %USERPROFILE%\.cache\huggingface, which can fail with
# "filename, directory name, or volume label syntax is incorrect" if the
# user profile path contains characters or symlinks HF doesn't grok. Using
# a sibling directory under the repo keeps things predictable.
_hf_cache_dir: Path = Path(os.getenv(
    "CorAi_HF_CACHE",
    str(Path(__file__).resolve().parent / ".hf_cache"),
))
_hf_cache_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(_hf_cache_dir))
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(_hf_cache_dir))


def _has_google_key() -> bool:
    """Re-read the API key from the environment on every check.

    Caching the value at import time made the chatbot say "needs a Google
    API key" even after the user set ``$env:GOOGLE_API_KEY = "..."`` in
    PowerShell, because the WSGI process had already imported this module
    before the key was exported.
    """
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key or key == "YOUR_GEMINI_API_KEY_HERE":
        return False
    return True


# Back-compat name used by callers that import ``_configured``. It always
# reads the current environment so we don't latch a stale value at import.
def _configured() -> bool:
    return _has_google_key()


def configure(
    google_api_key: str | None = None,
    embed_model: str | None = None,
    gemini_model: str | None = None,
    index_dir: str | Path | None = None,
) -> None:
    """Override RAG configuration at runtime (e.g. from the Flask app factory).

    Calling this with a non-empty ``google_api_key`` flips the module into
    "configured" mode and triggers lazy initialization of the RAG chain.
    """
    global _embed_model_name, _gemini_model_name, _index_dir
    if google_api_key:
        os.environ["GOOGLE_API_KEY"] = google_api_key
    if embed_model:
        _embed_model_name = embed_model
    if gemini_model:
        _gemini_model_name = gemini_model
    if index_dir is not None:
        _index_dir = Path(index_dir)
        _index_dir.mkdir(parents=True, exist_ok=True)


def is_configured() -> bool:
    """True when the RAG pipeline is *able* to answer questions.

    Probes the heavy deps on first call (cheap on subsequent calls). The
    probe is what makes the RAG chain bootable on Render free tier — the
    torch/transformers stack only loads when a chat request actually asks.
    """
    return _probe_deps() and _has_google_key()


def status() -> dict[str, Any]:
    """Debug snapshot — useful for a /healthz-style endpoint."""
    deps_ok = _probe_deps() if _RAG_DEPS_OK is None else _RAG_DEPS_OK
    return {
        "deps_ok": deps_ok,
        "deps_error": _import_error,
        "configured": deps_ok and _has_google_key(),
        "ready": deps_ok and _has_google_key() and _rag_chain is not None,
        "embed_model": _embed_model_name,
        "gemini_model": _gemini_model_name,
        "index_dir": str(_index_dir),
        "hf_cache": str(_hf_cache_dir),
    }


# --------------------------------------------------------------------------- #
# Pipeline construction
# --------------------------------------------------------------------------- #

def _build_chain() -> Any:
    """Build (or load) the FAISS index and the LangChain RAG chain.

    The on-disk cache is the small ``index.faiss`` + ``index.pkl`` pair that
    ``FAISS.save_local`` writes. We rebuild whenever the source text changes
    or the cache directory is empty.
    """
    if not _probe_deps():
        raise RuntimeError(
            f"rag_engine: missing dependencies ({_import_error}). "
            "Install langchain, langchain-community, langchain-google-genai, "
            "faiss-cpu, sentence-transformers."
        )
    if not _has_google_key():
        raise RuntimeError("GOOGLE_API_KEY is not set")

    # Imports are gated to first chat request to keep Render free-tier
    # workers within their 512 MB RAM cap. See _probe_deps for the rationale.
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_classic.chains.retrieval import create_retrieval_chain
    from langchain_classic.chains.combine_documents.stuff import create_stuff_documents_chain
    from langchain_core.prompts import ChatPromptTemplate

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=40)
    docs = text_splitter.create_documents([corai_kb_content])

    # Pin the embedding model's download cache to a directory we control,
    # so the default %USERPROFILE%\.cache\huggingface path doesn't trip on
    # Windows oddities (the cryptic "filename, directory name, or volume
    # label syntax is incorrect" error from the OS).
    embeddings = HuggingFaceEmbeddings(
        model_name=_embed_model_name,
        cache_folder=str(_hf_cache_dir),
    )
    index_path = _index_dir
    faiss_file = index_path / "index.faiss"
    pkl_file = index_path / "index.pkl"

    if faiss_file.exists() and pkl_file.exists():
        try:
            vectorstore = FAISS.load_local(
                str(index_path),
                embeddings,
                allow_dangerous_deserialization=True,
            )
            log.info("Loaded RAG index from %s", index_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to load RAG index (%s); rebuilding", exc)
            vectorstore = FAISS.from_documents(docs, embeddings)
            vectorstore.save_local(str(index_path))
    else:
        vectorstore = FAISS.from_documents(docs, embeddings)
        index_path.mkdir(parents=True, exist_ok=True)
        vectorstore.save_local(str(index_path))
        log.info("Built and persisted RAG index at %s", index_path)

    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    llm = ChatGoogleGenerativeAI(model=_gemini_model_name, temperature=0.2)

    system_prompt = (
        "You are CorAi's official HeartAI Copilot — a friendly, accurate "
        "assistant for the CorAi.\n"
        "Use the following context snippets to answer questions about CorAi "
        "accurately. If the answer is not contained within the context, say "
        "'I don't have that information right now.' and suggest the user "
        "check the project README or MODEL_CARD.\n\n"
        "Context:\n{context}"
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    qa_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(retriever, qa_chain)


def _ensure_chain() -> Any:
    """Build the chain on first use, then cache it for the process lifetime."""
    global _rag_chain
    if _rag_chain is not None:
        return _rag_chain
    with _lock:
        if _rag_chain is None:
            _rag_chain = _build_chain()
    return _rag_chain


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def get_bot_response(user_query: str) -> str:
    """Answer a user question using the RAG pipeline.

    Raises:
        RuntimeError: if dependencies are missing or the API key is not set.
    """
    chain = _ensure_chain()
    response = chain.invoke({"input": user_query})
    # create_retrieval_chain returns {"input", "context", "answer"}
    return response.get("answer", "")


def get_bot_response_safe(user_query: str) -> str:
    """Same as ``get_bot_response`` but never raises — returns a friendly
    fallback string instead. Useful for chat routes that prefer 200 OK with
    an explanatory message over a 500.
    """
    if not _probe_deps():
        return (
            "The RAG chatbot isn't fully wired up yet on this server "
            "(missing dependencies). The rest of CorAi is still working."
        )
    if not _has_google_key():
        return (
            "The HeartAI Copilot needs a Google API key to answer questions. "
            "Set GOOGLE_API_KEY in the environment to enable it."
        )
    try:
        return get_bot_response(user_query)
    except Exception as exc:  # noqa: BLE001
        log.exception("RAG chain failed")
        return f"Sorry, the assistant hit an error: {exc}"


# --------------------------------------------------------------------------- #
# Manual smoke test
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys
    if not _probe_deps():
        print("Missing deps:", _import_error)
        sys.exit(1)
    if not os.getenv("GOOGLE_API_KEY"):
        print("Set GOOGLE_API_KEY first.")
        sys.exit(1)
    q = " ".join(sys.argv[1:]) or "What does CorAi do?"
    print(get_bot_response(q))
