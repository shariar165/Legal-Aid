"""Corpus store + hybrid retrieval (BM25 over EN/BN tokens, multilingual-e5 dense vectors, RRF fusion).

Contracts are usually English while most BD statutes are Bangla, so lexical search alone
cannot bridge the languages; the dense model (intfloat/multilingual-e5-small) does.
Dense search is optional (AIN_DENSE=0 or missing embeddings -> BM25 only).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

from ain import config
from ain.models import Section

TOKEN_RE = re.compile(r"[a-z0-9ঀ-৿]+")
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
EMBED_MODEL = "intfloat/multilingual-e5-small"
STOP = {"the", "of", "and", "or", "to", "in", "a", "an", "any", "by", "for", "be", "is", "shall", "such", "as", "on", "with", "that", "this", "which", "under"}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower().translate(BN_DIGITS)) if t not in STOP]


def corpus_hash() -> str:
    return hashlib.sha256(config.CORPUS_FILE.read_bytes()).hexdigest()[:16]


class Corpus:
    def __init__(self, sections: list[Section]):
        self.sections = sections
        self.by_id = {s.citation_id: s for s in sections}
        self._bm25 = BM25Okapi([tokenize(f"{s.heading} {s.heading} {s.text}") for s in sections])
        self._emb: np.ndarray | None = None
        self._model = None
        if config.dense_enabled() and config.EMBEDDINGS_FILE.exists():
            meta = config.EMBEDDINGS_FILE.with_suffix(".json")
            if meta.exists() and json.loads(meta.read_text())["corpus_hash"] == corpus_hash():
                self._emb = np.load(config.EMBEDDINGS_FILE)

    # ------------------------------------------------------------- lookup
    def get(self, citation_id: str) -> Section | None:
        return self.by_id.get(citation_id)

    def __contains__(self, citation_id: str) -> bool:
        return citation_id in self.by_id

    # ------------------------------------------------------------- search
    @property
    def dense_ready(self) -> bool:
        return self._emb is not None

    def _encoder(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(EMBED_MODEL, device="cpu")
        return self._model

    def search(self, query: str, packs: set[str] | None = None, k: int = 8, include_repealed: bool = True) -> list[tuple[Section, float]]:
        idx = [i for i, s in enumerate(self.sections) if (not packs or set(s.packs) & packs) and (include_repealed or s.status != "repealed")]
        if not idx:
            return []
        ranks: dict[int, float] = {}
        bm = self._bm25.get_scores(tokenize(query))
        for r, i in enumerate(sorted(idx, key=lambda i: -bm[i])[: k * 4]):
            if bm[i] > 0:
                ranks[i] = ranks.get(i, 0.0) + 1.0 / (60 + r)
        if self._emb is not None:
            q = self._encoder().encode([f"query: {query}"], normalize_embeddings=True)[0]
            sims = self._emb[idx] @ q
            for r, j in enumerate(np.argsort(-sims)[: k * 4]):
                i = idx[j]
                ranks[i] = ranks.get(i, 0.0) + 1.0 / (60 + r)
        best = sorted(ranks.items(), key=lambda x: -x[1])[:k]
        return [(self.sections[i], score) for i, score in best]

    # ------------------------------------------------------------- recursive cross-references
    XREF_RE = re.compile(r"(?:section|sections|s\.|ধারা)\s*([0-9০-৯]+[A-Za-zকখগ]?)", re.I)

    def cross_refs(self, section: Section, limit: int = 4) -> list[Section]:
        """Sections of the same act referenced inside this section's text ("ধারা ১২৫", "section 28")."""
        out: list[Section] = []
        for raw in self.XREF_RE.findall(section.text):
            no = raw.translate(BN_DIGITS).replace("ক", "A").replace("খ", "B").replace("গ", "C").upper()
            ref = self.by_id.get(f"{section.act_key}-s{no}")
            if ref and ref.citation_id != section.citation_id and ref not in out:
                out.append(ref)
            if len(out) >= limit:
                break
        return out


def nfc(text: str) -> str:
    """Bangla letters such as য় / ড় exist both composed and decomposed; compare everything in NFC."""
    return unicodedata.normalize("NFC", text)


def _load_sections() -> list[Section]:
    out = []
    for line in config.CORPUS_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            rec["text"], rec["heading"] = nfc(rec["text"]), nfc(rec["heading"])
            out.append(Section(**rec))
    return out


class CorpusOverlay:
    """One job's view of the corpus: the shared statutes plus sections that exist only for this job
    (the clauses of an uploaded employer policy). Extra sections resolve by citation_id, so the verifier
    checks quotes against them like any statute, but they are not searched: the agents that need them
    get them directly."""

    def __init__(self, base: Corpus, extra: list[Section]):
        self._base = base
        self.extra = {s.citation_id: s for s in extra}

    def get(self, citation_id: str) -> Section | None:
        return self.extra.get(citation_id) or self._base.get(citation_id)

    def __contains__(self, citation_id: str) -> bool:
        return citation_id in self.extra or citation_id in self._base

    def __getattr__(self, name: str):
        return getattr(self._base, name)


@lru_cache
def get_corpus() -> Corpus:
    return Corpus(_load_sections())


def build_embeddings() -> None:
    """Encode every section once (CPU, ~1-2 min) and store vectors next to the corpus."""
    from sentence_transformers import SentenceTransformer

    sections = _load_sections()
    model = SentenceTransformer(EMBED_MODEL, device="cpu")
    texts = [f"passage: {s.act_en} s.{s.section} {s.heading}. {s.text[:1500]}" for s in sections]
    emb = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True)
    np.save(config.EMBEDDINGS_FILE, emb.astype(np.float32))
    config.EMBEDDINGS_FILE.with_suffix(".json").write_text(json.dumps({"model": EMBED_MODEL, "corpus_hash": corpus_hash(), "n": len(sections)}))
    print(f"embedded {len(sections)} sections -> {config.EMBEDDINGS_FILE}")


if __name__ == "__main__":
    build_embeddings()
