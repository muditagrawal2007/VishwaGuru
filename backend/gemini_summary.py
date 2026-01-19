"""
Gemini Summary Service for Maharashtra MLA Information

Uses Gemini AI to generate human-readable summaries about MLAs and their roles.
"""
import os
import google.generativeai as genai
from typing import Dict, Optional, Callable, Any
import warnings
from async_lru import alru_cache
import logging
import asyncio

# Suppress deprecation warnings from google.generativeai
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")

logger = logging.getLogger(__name__)

async def retry_with_exponential_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    *args,
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: The async function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Factor to multiply delay by each retry
        *args, **kwargs: Arguments to pass to the function

    Returns:
        The result of the function call

    Raises:
        The last exception encountered if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if attempt == max_retries:
                # Last attempt failed, re-raise the exception
                logger.error(f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}")
                raise e

            # Calculate delay with exponential backoff
            delay = min(base_delay * (backoff_factor ** attempt), max_delay)

            logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {delay:.1f}s")
            await asyncio.sleep(delay)

    # This should never be reached, but just in case
    raise last_exception

# Configure Gemini (mandatory environment variable)
api_key = os.environ.get("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
else:
    # Gemini disabled (mock/local mode)
    genai = None

def _get_fallback_summary(mla_name: str, assembly_constituency: str, district: str) -> str:
    """
    Generate a fallback summary when Gemini is unavailable or fails.
    
    Args:
        mla_name: Name of the MLA
        assembly_constituency: Assembly constituency name
        district: District name
        
    Returns:
        A simple fallback description
    """
    return (
        f"{mla_name} represents the {assembly_constituency} assembly constituency "
        f"in {district} district, Maharashtra. MLAs handle local issues such as "
        f"infrastructure, public services, and constituent welfare."
    )


@alru_cache(maxsize=100)
async def generate_mla_summary(
    district: str,
    assembly_constituency: str,
    mla_name: str,
    issue_category: Optional[str] = None
) -> str:
    """
    Generate a human-readable summary about an MLA using Gemini with retry logic.

    Args:
        district: District name
        assembly_constituency: Assembly constituency name
        mla_name: Name of the MLA
        issue_category: Optional category of issue for context

    Returns:
        A short paragraph describing the MLA's role and responsibilities
    """
    async def _generate_mla_summary_with_gemini() -> str:
        """Inner function to generate MLA summary with Gemini"""
        model = genai.GenerativeModel('gemini-1.5-flash')

        issue_context = f" particularly regarding {issue_category} issues" if issue_category else ""

        prompt = f"""
        You are helping an Indian citizen understand who represents them.
        In one short paragraph (max 100 words), explain that the MLA {mla_name} represents
        the assembly constituency {assembly_constituency} in district {district}, state Maharashtra{issue_context},
        and what type of local issues they typically handle.

        Do not hallucinate phone numbers or emails; only talk about roles and responsibilities.
        Keep it factual, helpful, and encouraging for civic engagement.
        """

        response = await model.generate_content_async(prompt)
        return response.text.strip()

    try:
        return await retry_with_exponential_backoff(_generate_mla_summary_with_gemini, max_retries=2)
    except Exception as e:
        logger.error(f"Gemini MLA summary generation failed after retries: {e}")
        # Fallback to simple description
        return _get_fallback_summary(mla_name, assembly_constituency, district)
