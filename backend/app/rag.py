"""RAG engine: resume parsing, chunking, embeddings, retrieval, PII masking, JD templates."""
import glob
import hashlib
import math
import os
import re

import chromadb

from .config import CHROMA_DIR, EMBEDDINGS, TEMPLATE_DIR

_client = chromadb.PersistentClient(path=CHROMA_DIR)


class HashEmbedding(chromadb.EmbeddingFunction):
    """Tiny offline bag-of-words embedding so the project runs without model downloads."""
    def __init__(self): pass
    @staticmethod
    def name(): return "hash-embedding"
    def get_config(self): return {}
    @staticmethod
    def build_from_config(config): return HashEmbedding()

    def __call__(self, input):
        out = []
        for text in input:
            v = [0.0] * 256
            for w in re.findall(r"[a-z0-9+#.]+", text.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 256] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


def _col(name):
    ef = HashEmbedding() if EMBEDDINGS == "hash" else None
    kw = {"embedding_function": ef} if ef else {}
    return _client.get_or_create_collection(name, **kw)


def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        import fitz
        with fitz.open(path) as doc:
            return "\n".join(p.get_text() for p in doc)
    if ext == ".docx":
        import docx
        return "\n".join(p.text for p in docx.Document(path).paragraphs)
    return open(path, encoding="utf-8", errors="ignore").read()


def guess_contact(text: str, filename: str):
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    email = m.group(0) if m else ""
    first = next((l.strip() for l in text.splitlines() if l.strip()), "")
    name = first if 1 <= len(first.split()) <= 4 and "@" not in first else os.path.splitext(filename)[0]
    return name, email


def mask_pii(text: str) -> str:
    """Bias reduction: remove contact data before the LLM sees a resume chunk."""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
    text = re.sub(r"\+?\d[\d\s().-]{8,}\d", "[phone]", text)
    return text


def chunk(text: str, size=700, overlap=120):
    paras, chunks, cur = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()], [], ""
    for p in paras:
        if len(cur) + len(p) > size and cur:
            chunks.append(cur)
            cur = cur[-overlap:] + "\n" + p
        else:
            cur = (cur + "\n" + p).strip()
    return chunks + [cur] if cur else chunks


def ingest_resume(thread_id: str, cand_id: str, text: str):
    parts = chunk(mask_pii(text)) or [text[:700]]
    _col("resumes").add(
        ids=[f"{cand_id}-{i}" for i in range(len(parts))],
        documents=parts,
        metadatas=[{"thread_id": thread_id, "cand_id": cand_id}] * len(parts),
    )


def retrieve(thread_id: str, cand_id: str, query: str, k=2):
    col = _col("resumes")
    r = col.query(query_texts=[query], n_results=k,
                  where={"$and": [{"thread_id": thread_id}, {"cand_id": cand_id}]})
    docs = r["documents"][0] if r["documents"] else []
    dist = r["distances"][0] if r.get("distances") else []
    return docs, dist


def jd_templates(query: str, k=2):
    col = _col("jd_templates")
    if col.count() == 0:
        files = glob.glob(os.path.join(TEMPLATE_DIR, "*.txt"))
        if not files:
            return []
        col.add(ids=[os.path.basename(f) for f in files],
                documents=[open(f, encoding="utf-8").read() for f in files])
    return col.query(query_texts=[query], n_results=min(k, col.count()))["documents"][0]
