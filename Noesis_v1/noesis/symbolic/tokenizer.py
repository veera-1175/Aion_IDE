"""Step 7 — Tokenization using SentencePiece symbolic vocabulary."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SymbolicTokenizer:
    """
    SentencePiece-based tokenizer for compact symbolic representation.
    Trains a small vocab on first use if model doesn't exist.
    """

    def __init__(self, model_path: str, vocab_size: int = 8000):
        self.model_path = Path(model_path)
        self.vocab_size = vocab_size
        self._sp = None

    @property
    def sp(self):
        if self._sp is None:
            import sentencepiece as spm
            if not self.model_path.exists():
                self._train_default_model()
            self._sp = spm.SentencePieceProcessor()
            self._sp.load(str(self.model_path))
        return self._sp

    def encode(self, text: str) -> list[int]:
        return self.sp.encode(text, out_type=int)

    def decode(self, token_ids: list[int]) -> str:
        return self.sp.decode(token_ids)

    def _train_default_model(self) -> None:
        """Bootstrap a minimal SentencePiece model for offline use."""
        import sentencepiece as spm

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        corpus_path = self.model_path.parent / "tokenizer_corpus.txt"

        # Seed corpus for technical/memory domain
        seed = [
            "Backend scalability expertise with FastAPI and Redis",
            "User deployed Redis cluster for API caching",
            "Async worker bottleneck in production deployment",
            "Docker Redis Nginx Gunicorn deployment sequence",
            "Semantic memory compression and knowledge graph",
            "Distributed AI cognition edge synchronization",
            "Episodic semantic procedural insight memory categories",
            "FastAPI async scaling Redis cache worker bottleneck",
            "Knowledge graph construction and associative recall",
            "Portable memory packets with bytecode compression",
            "Importance scoring and semantic abstraction layers",
            "Machine learning transformers embeddings neural networks",
        ] * 100

        corpus_path.write_text("\n".join(seed), encoding="utf-8")
        prefix = str(self.model_path.with_suffix(""))

        # Cap vocab to corpus capacity (SentencePiece requires vocab <= unique tokens)
        effective_vocab = min(self.vocab_size, 512)

        spm.SentencePieceTrainer.train(
            input=str(corpus_path),
            model_prefix=prefix,
            vocab_size=effective_vocab,
            model_type="bpe",
            character_coverage=0.9995,
            pad_id=0,
            unk_id=1,
            bos_id=2,
            eos_id=3,
        )
        logger.info("Trained symbolic tokenizer at %s", self.model_path)
