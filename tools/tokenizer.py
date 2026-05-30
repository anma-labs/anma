"""Token counting. Uses tiktoken if available, falls back to len(text) // 4."""

_encoder = None
_use_tiktoken = None

def count_tokens(text):
    global _encoder, _use_tiktoken
    if _use_tiktoken is None:
        try:
            import tiktoken
            _encoder = tiktoken.get_encoding('cl100k_base')
            _use_tiktoken = True
        except Exception:
            _use_tiktoken = False
    if _use_tiktoken:
        return len(_encoder.encode(text))
    return len(text) // 4
