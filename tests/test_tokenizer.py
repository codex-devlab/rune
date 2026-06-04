from rune.pipeline.tokenizer import count_tokens, split_into_chunks


def test_count_tokens_returns_int():
    n = count_tokens("hello world")
    assert isinstance(n, int)
    assert n > 0


def test_count_tokens_empty():
    assert count_tokens("") == 0


def test_split_into_chunks_non_empty():
    text = "# Header\n\nFirst paragraph.\n\n# Header 2\n\nSecond paragraph.\n"
    chunks = split_into_chunks(text)
    assert len(chunks) >= 2
    assert all(c.token_count > 0 for c in chunks)


def test_split_into_chunks_empty_text():
    chunks = split_into_chunks("")
    assert chunks == []


def test_chunks_cover_full_text(tmp_path):
    text = "line1\nline2\nline3\n"
    chunks = split_into_chunks(text)
    combined = " ".join(c.text for c in chunks)
    assert "line1" in combined
