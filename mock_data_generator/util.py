"""Some utility functions for the mock data generator."""

from typing import Callable, Optional


def ask_user(prompt: str) -> bool:
    """Prompt the user with a yes/no question and return if the response is affirmative."""
    return input(prompt).lower() == "y"


def get_response(
    prompt: str,
    default: str = "",
    allow_empty: bool = True,
    condition: Optional[Callable[[str], bool]] = None,
) -> str:
    """Prompt the user for a response with various enhancements.

    Args:
        prompt: The message to display to the user.
        default: The default value to use if the user provides no input.
        allow_empty: Whether the user can provide an empty response (which causes default to be returned).
        condition: A function that takes the response and returns whether it is valid.
                   If the condition is not met, the user will be prompted again.
    """
    initial_response = _get_response(prompt, default, allow_empty)
    if condition is None:
        return initial_response
    if condition(initial_response):
        return initial_response
    print("Response did not meet conditions.  Please try again...")
    return get_response(prompt, default, allow_empty, condition)


def _get_response(
    prompt: str,
    default: str = "",
    allow_empty: bool = True,
):
    response = input(prompt)
    if response:
        return response
    if default:
        return default
    if not allow_empty:
        print("You must provide a response to this prompt!")
        return get_response(prompt, default, allow_empty)
    return ""
