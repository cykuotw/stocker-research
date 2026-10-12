"""A console-only tool for the echo sanity test."""

from langchain_core.tools import tool


@tool
def print_user_message(message: str) -> str:
    """Print the user's greeting verbatim to the backend console.

    Args:
        message: The user's greeting text, without rewriting or extra commentary.
    """
    print(message, flush=True)
    return message
