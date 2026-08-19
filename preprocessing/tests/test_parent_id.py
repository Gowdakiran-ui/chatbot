from parent_id import chapter_group_key, compute_parent_id


def test_chapter_group_key_book_and_chapter():
    assert chapter_group_key("arthashastra", "Book II, Chapter XXX") == "arthashastra_book_ii_chapter_xxx"


def test_chapter_group_key_chapter_only_drops_verse():
    assert chapter_group_key("chanakya_neeti", "Chapter 3, Verse 3.35") == "chanakya_neeti_chapter_3"


def test_chapter_group_key_range_uses_first_chapter():
    ref = "Book VII, Chapter XII–Book VII, Chapter XIII"
    assert chapter_group_key("arthashastra", ref) == "arthashastra_book_vii_chapter_xii"


def test_chapter_group_key_untitled_returns_none():
    assert chapter_group_key("chanakya_neeti", "untitled") is None


def test_compute_parent_id_verse_type():
    row = {"chunk_type": "verse", "source": "arthashastra", "reference": "Book II, Chapter XXX"}
    assert compute_parent_id(row) == "arthashastra_book_ii_chapter_xxx"


def test_compute_parent_id_prose_type_is_none():
    row = {"chunk_type": "prose", "source": "corporate_chanakya", "reference": "segment 24"}
    assert compute_parent_id(row) is None


def test_compute_parent_id_verse_type_without_book_or_chapter_is_none():
    row = {"chunk_type": "verse", "source": "chanakya_neeti", "reference": "untitled"}
    assert compute_parent_id(row) is None
