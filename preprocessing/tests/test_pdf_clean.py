from pdf_clean import (
    clean_pages,
    detect_repeated_lines,
    drop_non_alpha_pages,
    find_back_matter_start,
    find_front_matter_end,
    is_page_number_line,
    non_alpha_ratio,
    strip_header_footer_and_page_numbers,
)


def test_detect_repeated_lines_above_threshold():
    pages = ["Header\nBody A", "Header\nBody B", "Header\nBody C", "Different\nBody D"]
    repeated = detect_repeated_lines(pages, threshold=0.30)
    assert "Header" in repeated
    assert "Different" not in repeated


def test_is_page_number_line():
    assert is_page_number_line("42")
    assert is_page_number_line(" - 12 - ")
    assert is_page_number_line("xiv")
    assert not is_page_number_line("Chapter 12: The King")


def test_strip_header_footer_and_page_numbers():
    pages = [
        "Header\nPage one unique content\n12",
        "Header\nPage two different text\n13",
        "Header\nPage three other words\n14",
        "Header\nPage four more text\n15",
    ]
    repeated = detect_repeated_lines(pages, threshold=0.30)
    cleaned, log = strip_header_footer_and_page_numbers(pages, repeated)
    assert "Header" not in cleaned[0]
    assert "12" not in cleaned[0].split("\n")
    assert "Page one unique content" in cleaned[0]
    assert len(log) == 2  # header/footer log + page-number log


def test_non_alpha_ratio():
    assert non_alpha_ratio("1234567890") == 1.0
    assert non_alpha_ratio("hello world") == 0.0
    assert 0.4 < non_alpha_ratio("abc123") < 0.6


def test_drop_non_alpha_pages():
    pages = ["Normal prose content here.", "12345 --- ### 6789"]
    kept, dropped = drop_non_alpha_pages(pages, threshold=0.8)
    assert dropped == [1]
    assert kept[0] == pages[0]
    assert kept[1] == ""


def test_find_front_matter_end():
    short_page = "Title Page"
    substantive = " ".join(["word"] * 250)
    pages = [short_page, short_page, substantive]
    assert find_front_matter_end(pages, word_threshold=200) == 2


def test_find_back_matter_start():
    substantive = " ".join(["word"] * 250)
    short_page = "Index"
    pages = [substantive, short_page, short_page]
    assert find_back_matter_start(pages, word_threshold=200) == 1


def _substantive_page(seed: str) -> str:
    # Varied multi-line prose (not a single repeated line) so header/footer detection
    # doesn't mistake the whole page body for a repeated header.
    return "\n".join(f"{seed} paragraph line {i} with distinct filler words" for i in range(40))


def test_clean_pages_trims_front_and_back_matter():
    pages = [
        "Title Page",
        "Copyright Notice",
        _substantive_page("alpha"),
        _substantive_page("beta"),
        "Index",
        "About the Author",
    ]
    cleaned_text, log = clean_pages(pages)
    assert "Title Page" not in cleaned_text
    assert "Index" not in cleaned_text
    assert "alpha paragraph" in cleaned_text
    assert "beta paragraph" in cleaned_text
    actions = {entry.action for entry in log}
    assert "trim_front" in actions
    assert "trim_back" in actions


def test_clean_pages_does_not_over_trim_short_document():
    # A document with no page crossing the word threshold should be kept whole,
    # not trimmed down to nothing.
    pages = ["Some short content on page one.", "Some more short content on page two."]
    cleaned_text, _ = clean_pages(pages)
    assert "Some short content" in cleaned_text
    assert "Some more short content" in cleaned_text
