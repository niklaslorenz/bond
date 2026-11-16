"""Fuzzy-matching helpers for the file system tools.

Access policy (path resolution, permission checks, the AuthorizedPath
wrapper) lives in :mod:`bond.fs_access` — tools get access exclusively via
``ToolCallContext.request_fs_access``.
"""

import difflib


def normalize(text: str) -> str:
    """Normalize text for fuzzy comparison."""
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def fuzzy_find_aider_patch_blocks(text: str, search: str) -> tuple[int, int] | None:
    """
    Find best approximate match of search block in text.
    Used for multi-line block matching (e.g., aider SEARCH/REPLACE blocks).
    Returns (start_index, end_index) or None.
    """
    norm_search = normalize(search)
    text_lines = text.splitlines()
    search_lines = search.splitlines()

    best_ratio = 0
    best_span = None

    for i in range(len(text_lines)):
        window = text_lines[i : i + len(search_lines)]
        if not window:
            continue

        candidate = "\n".join(window)
        ratio = difflib.SequenceMatcher(None, normalize(candidate), norm_search).ratio()

        if ratio > best_ratio:
            best_ratio = ratio
            best_span = (i, i + len(search_lines))

    if best_ratio > 0.85:
        return best_span

    return None


def fuzzy_contains(text: str, search: str, threshold: float = 0.6) -> bool:
    """
    Check if search string is approximately contained in text.
    Used for single-line fuzzy matching.
    
    Args:
        text: The text to search in (typically a single line)
        search: The pattern to search for
        threshold: Minimum similarity ratio (0.0 to 1.0) to consider a match
    
    Returns:
        True if search is fuzzy-matched in text, False otherwise
    """
    if not search:
        return True
    if not text:
        return False
    
    # Use SequenceMatcher to find the best match of search within text
    # Check all possible substrings of text to find the best match
    search_len = len(search)
    text_len = len(text)
    
    # If search is longer than text, compare the whole strings
    if search_len > text_len:
        ratio = difflib.SequenceMatcher(None, text, search).ratio()
        return ratio >= threshold
    
    # Find the best matching substring in text
    best_ratio = 0.0
    # Check all possible window sizes from search_len to text_len
    # But for efficiency, we'll check windows of size search_len and also the full text
    
    # First, check windows of the same length as search
    if search_len > 0:
        for i in range(len(text) - search_len + 1):
            window = text[i:i + search_len]
            ratio = difflib.SequenceMatcher(None, window, search).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                if best_ratio >= threshold:
                    return True
    
    # Also check the entire text against the search
    ratio = difflib.SequenceMatcher(None, text, search).ratio()
    if ratio > best_ratio:
        best_ratio = ratio
    
    return best_ratio >= threshold
