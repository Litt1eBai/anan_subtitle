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


def replace_sentence_initial_wo(text: str) -> str:
    if not text:
        return ""
    return text.replace("我", "吾辈")
