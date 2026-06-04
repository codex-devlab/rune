from rune.models.source import Chunk

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))

except ImportError:
    def count_tokens(text: str) -> int:
        # fallback: ~4 chars per token (±10% accuracy)
        return max(0, len(text) // 4)


def split_into_chunks(text: str) -> list[Chunk]:
    """Split text on blank lines into paragraph chunks."""
    if not text.strip():
        return []

    paragraphs = text.split("\n\n")
    chunks: list[Chunk] = []
    current_line = 1

    for para in paragraphs:
        para = para.strip()
        if not para:
            current_line += 2
            continue
        line_count = para.count("\n") + 1
        token_count = count_tokens(para)
        chunks.append(
            Chunk(
                text=para,
                start_line=current_line,
                end_line=current_line + line_count - 1,
                token_count=token_count,
            )
        )
        current_line += line_count + 1  # +1 for blank line separator

    return chunks
