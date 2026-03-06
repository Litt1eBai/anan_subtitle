def merge_incremental_text(current: str, new_text: str) -> str:
    new_clean = new_text.strip()
    if not new_clean:
        return current
    if not current:
        return new_clean

    if new_clean.startswith(current):
        return new_clean
    if current.endswith(new_clean):
        return current

    max_overlap = min(len(current), len(new_clean))
    for overlap in range(max_overlap, 0, -1):
        if current.endswith(new_clean[:overlap]):
            return current + new_clean[overlap:]
    return current + new_clean
