"""Kimi (Moonshot AI) API client using kimi-sdk.

Simple client wrapper around kimi-sdk with retry support.
Supports dynamic model switching for fallback scenarios.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass

from kimi_sdk import Kimi, Message, generate

logger = logging.getLogger(__name__)


# Retryable HTTP status codes
RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


class KimiAPIError(Exception):
    """Raised when Kimi API call fails."""
    def __init__(self, message: str, retries: int = 0, last_error: Exception = None):
        super().__init__(message)
        self.retries = retries
        self.last_error = last_error


@dataclass
class TokenUsage:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class KimiClient:
    """Client for Kimi API using kimi-sdk.
    
    Supports dynamic model switching for fallback scenarios.
    """

    BASE_URL = "https://api.moonshot.cn/v1"

    def __init__(self, api_key: str, model: str = "kimi-k2-turbo-preview"):
        """Initialize Kimi client.
        
        Args:
            api_key: Kimi API key (required)
            model: Model name (default: kimi-k2-turbo-preview)
        """
        if not api_key:
            raise ValueError("KIMI_API_KEY is required")

        self.api_key = api_key
        self._model = model
        self._kimi = Kimi(
            base_url=self.BASE_URL,
            api_key=self.api_key,
            model=self._model,
            stream=False,  # Use non-streaming for simpler response handling
        )

        logger.info(f"Initialized KimiClient with model: {self._model}")

    @property
    def model(self) -> str:
        """Get current model name."""
        return self._model

    @model.setter
    def model(self, value: str):
        """Set model name (for fallback switching)."""
        if value != self._model:
            logger.info(f"Switching model: {self._model} -> {value}")
            self._model = value
            # Recreate Kimi instance with new model
            self._kimi = Kimi(
                base_url=self.BASE_URL,
                api_key=self.api_key,
                model=self._model,
                stream=False,
            )

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable."""
        error_str = str(error).lower()

        # Check for retryable status codes
        for code in RETRYABLE_STATUS_CODES:
            if str(code) in error_str:
                return True

        # Check for connection/timeout errors
        retryable_keywords = ["timeout", "connection", "temporarily", "overloaded", "rate limit"]
        return any(kw in error_str for kw in retryable_keywords)

    def chat(
        self,
        messages: list,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        retries: int = 3
    ) -> str:
        """Send chat completion request to Kimi with exponential backoff retry.
        
        Args:
            messages: Chat messages (list of dicts with 'role' and 'content')
            max_tokens: Maximum tokens for response (default: 4096 for code review)
            temperature: Sampling temperature (default: 0.2 for consistent output)
            retries: Number of retry attempts
        
        Returns:
            Response content string
            
        Raises:
            KimiAPIError: If API call fails after all retries
        """
        # Convert dict messages to kimi-sdk Message objects
        sdk_messages = []
        system_prompt = None
        
        for msg in messages:
            if isinstance(msg, dict):
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    system_prompt = content
                else:
                    sdk_messages.append(Message(role=role, content=content))
            elif isinstance(msg, Message):
                sdk_messages.append(msg)
            else:
                raise ValueError(f"Invalid message type: {type(msg)}")

        last_error = None

        for attempt in range(retries + 1):
            try:
                logger.info(f"Calling Kimi API (attempt {attempt + 1}/{retries + 1}, model: {self._model})")
                
                # Run async generate - handle both cases: with and without existing event loop
                async def _generate():
                    result = await generate(
                        chat_provider=self._kimi,
                        system_prompt=system_prompt or "",
                        tools=[],  # No tools for simple chat
                        history=sdk_messages,
                    )
                    return result
                
                # Try to get existing event loop, create new one if none exists
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context, need to use different approach
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _generate())
                        result = future.result()
                except RuntimeError:
                    # No running event loop, safe to use asyncio.run()
                    result = asyncio.run(_generate())

                # Log token usage if available
                if result.usage:
                    usage = result.usage
                    prompt_tokens = getattr(usage, 'input', 0) or getattr(usage, 'input_other', 0)
                    completion_tokens = getattr(usage, 'output', 0)
                    total_tokens = prompt_tokens + completion_tokens
                    logger.info(
                        f"Token usage - prompt: {prompt_tokens}, "
                        f"completion: {completion_tokens}, "
                        f"total: {total_tokens}"
                    )

                # Extract text from response message
                return result.message.extract_text() or ""

            except Exception as e:
                last_error = e
                logger.warning(f"Kimi API call failed (attempt {attempt + 1}): {e}")

                if attempt < retries and self._is_retryable_error(e):
                    # Exponential backoff with jitter
                    delay = min(0.5 * (2 ** attempt), 10.0)
                    delay += random.uniform(0, 0.5 * delay)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                elif attempt < retries:
                    # Non-retryable error, stop retrying
                    logger.error(f"Non-retryable error: {e}")
                    break

        error_msg = f"Kimi API call failed (after {retries} retries): {str(last_error)}"
        logger.error(error_msg)
        raise KimiAPIError(error_msg, retries=retries, last_error=last_error)
