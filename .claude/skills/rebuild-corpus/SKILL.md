---
name: rebuild-corpus
description: Rebuild Ain Copilot's law corpus and embeddings after a source, excerpt marker, country or company entry changes. Use when corpus.jsonl must be regenerated or a corpus test fails after editing corpus/ or countries.yaml.
---

# Rebuild the law corpus

Run from `backend/` with the root `.venv` active. Never edit `corpus/processed/*.jsonl` by hand, and never type
statute text or section numbers: everything comes from the official sources these scripts download.

1. `python -m corpus.fetch_intl`: download international and country sources into `corpus/raw/` (gitignored).
2. `python -m corpus.curate_intl`: cut the verbatim excerpts. It fails loudly on a missing marker; fix the marker
   in the script, not the text.
3. `python -m corpus.curate_companies`: companies' own published policies (`corpus/companies.yaml`).
4. `python -m corpus.build_corpus`: merge everything into `corpus/processed/corpus.jsonl`.
5. `python -m ain.retrieval`: incremental dense embeddings; only new or changed sections are encoded. If it runs
   out of memory (exit 139) on a small machine, re-encode with `batch_size=1`.
6. `python -m pytest -q tests/test_corpus.py tests/test_statute_text.py tests/test_countries.py`: every playbook
   anchor exists and every quote is verbatim.

Report the section count before and after, and any section whose text changed (the currency gate depends on it).
