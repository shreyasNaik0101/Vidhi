"""Live ingestion: run the pipeline on a pasted amendment, streaming each stage.

The read side stays in Node/Express; this Python service owns the write/ingest path
(pymupdf-free text in, classify → parse → apply → persist), because that is where
the pipeline and the local model already live.
"""
