"""Token counting for budgets and cost.

Budgets are measured with the cl100k_base tokenizer of tiktoken when it is
installed (pip install tiktoken), and with len(text) / 4 otherwise. Use the same
counter in every run of a comparison; the counter used is written to the results.
The token counts that the model reports (prompt_tokens) are stored as well.
"""
try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    COUNTER = "cl100k"

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except Exception:  # tiktoken missing or its files not downloadable
    COUNTER = "chars/4"

    def count_tokens(text: str) -> int:
        return max(1, (len(text) + 3) // 4)
