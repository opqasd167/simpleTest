def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Fixed-size character chunks with overlap, so a sentence is not lost at a boundary."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step) if text[i:i + size].strip()]
