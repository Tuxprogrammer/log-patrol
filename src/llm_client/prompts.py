"""Prompt construction for patrol LLM classification."""

from __future__ import annotations


def build_prompt(service: str, cleaned_message: str) -> str:
    """Build the verdict prompt sent to the LLM classifier.

    Args:
        service: Service name associated with the log line.
        cleaned_message: Sanitized log text sent to the model.

    Returns:
        The complete prompt string for the yes-or-no classifier.
    """
    return (
        'You are a log analyst. Answer only with "yes" or "no".\n'
        'Classify whether this single log line is issue-worthy/actionable.\n'
        'yes = failure, exception, stack trace, parser failure, auth '
        'failure (including Windows event_id 4625), or service unavailable.\n'
        'no = routine info/debug activity, expected queue/cron logs, '
        'HTTP 2xx access logs, or firewall match/pass flow lines.\n\n'
        f'Service: {service}\n'
        f'Log: {cleaned_message}\n\n'
        'Answer:'
    )
