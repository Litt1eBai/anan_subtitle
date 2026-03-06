from typing import Any

def extract_text(result: Any) -> str:
    if result is None:
        return ""

    current = result
    if isinstance(current, list):
        if not current:
            return ""
        current = current[0]

    if isinstance(current, dict):
        text = current.get("text")
        if isinstance(text, str):
            return text.strip()

        sentence_info = current.get("sentence_info")
        if isinstance(sentence_info, list):
            pieces = []
            for item in sentence_info:
                if isinstance(item, dict):
                    sentence_text = item.get("text")
                    if sentence_text:
                        pieces.append(str(sentence_text))
            merged = "".join(pieces).strip()
            if merged:
                return merged

        for key in ("result", "value", "preds"):
            value = current.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return str(current).strip()

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

def replace_sentence_initial_wo(text: str) -> str:
    if not text:
        return ""
    return text.replace("我", "吾辈")
