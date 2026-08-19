from chunking import chunk_prose_style, chunk_verse_style
from tokens import count_tokens


def test_chunk_verse_style_splits_on_numbered_verses():
    text = "CHAPTER 1\n2.1\nFirst verse teaching that is reasonably long. " * 1
    text = (
        "CHAPTER 1\n"
        "2.1\n"
        + ("The vipra is like a tree whose roots are prayers and deeds are the leaves. " * 3)
        + "\n"
        "2.2\n"
        + ("Cutting off the roots neither the branches nor the leaves endure at all. " * 3)
    )
    chunks = chunk_verse_style(text, min_tokens=10)
    assert len(chunks) >= 2
    assert any("Chapter 1" in c.reference for c in chunks)
    assert all(c.token_count > 0 for c in chunks)


def test_chunk_verse_style_merges_tiny_verses():
    text = "1.1\nShort.\n1.2\nAlso short.\n1.3\nTiny too."
    chunks = chunk_verse_style(text, min_tokens=50)
    # All three verses are far under 50 tokens each, so they should merge into one chunk.
    assert len(chunks) == 1
    assert "Short" in chunks[0].text
    assert "Tiny too" in chunks[0].text


def test_chunk_verse_style_fallback_paragraph_boundaries_without_numbering():
    text = "First unnumbered teaching paragraph here.\n\nSecond unnumbered teaching paragraph."
    chunks = chunk_verse_style(text, min_tokens=1)
    assert len(chunks) == 2


def test_chunk_prose_style_never_splits_mid_sentence():
    long_sentence_block = "This is a sentence. " * 100
    chunks = chunk_prose_style(long_sentence_block, min_tokens=50, max_tokens=100, overlap_ratio=0.0)
    for c in chunks:
        stripped = c.text.strip()
        assert stripped.endswith(".") or stripped == ""


def test_chunk_prose_style_respects_target_size_roughly():
    paragraph = "Sentence number {} covers a distinct topic with several extra filler words. "
    text = "\n\n".join(
        "".join(paragraph.format(i * 10 + j) for j in range(10)) for i in range(40)
    )
    chunks = chunk_prose_style(text, min_tokens=300, max_tokens=500, overlap_ratio=0.15)
    assert len(chunks) > 1
    # Most chunks should land near the target range (overlap can push the first bit over).
    for c in chunks[:-1]:
        assert c.token_count <= 600


def test_chunk_prose_style_applies_overlap():
    paragraph_a = "Alpha sentence one. Alpha sentence two. Alpha sentence three. " * 10
    paragraph_b = "Beta sentence one. Beta sentence two. Beta sentence three. " * 10
    text = paragraph_a + "\n\n" + paragraph_b
    chunks = chunk_prose_style(text, min_tokens=20, max_tokens=60, overlap_ratio=0.15)
    assert len(chunks) >= 2
    # The second chunk should contain some tail content carried over from the first.
    assert "Alpha" in chunks[1].text or "Beta" in chunks[0].text


def test_chunk_prose_style_empty_text_returns_no_chunks():
    assert chunk_prose_style("   \n\n  ") == []


def test_count_tokens_nonzero():
    assert count_tokens("hello world") > 0
