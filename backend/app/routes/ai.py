from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
import openai
import os
import json
import re
from typing import Dict, Any

# Import authentication dependency
from ..auth import get_current_user

router = APIRouter()

# Get OpenAI API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

class ExpandRequest(BaseModel):
    text: str

class ExpandResponse(BaseModel):
    expanded_query: str
    expanded_query_lucene: str

def sanitize_lucene_query(query: str) -> str:
    """Sanitize Lucene query string for security."""
    if len(query) > 1024:
        raise HTTPException(status_code=400, detail="Query too long (max 1024 characters)")
    
    # Remove control characters
    query = re.sub(r'[\x00-\x1f\x7f]', '', query)
    
    return query

@router.post("/expand", response_model=ExpandResponse)
async def expand_query(request: ExpandRequest, user_id: str = Depends(get_current_user)):
    """
    Expand a short topic text using GPT-4o to produce both comma-separated terms
    and a Lucene boolean query.
    """
    try:
        # Sanitize input
        if len(request.text.strip()) < 1:
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        if len(request.text) > 200:
            raise HTTPException(status_code=400, detail="Text too long (max 200 characters)")
        
        # Prepare the prompt for GPT-4o
        system_prompt = """You are a query normalizer. Given a short topic text, produce both:
1. expanded_query: 5-12 short related terms, comma-separated, no quotes, no operators.
2. expanded_query_lucene: the same set but as a Lucene boolean query using explicit OR, quoting multi-word phrases, escaping special characters, no commas.

Rules for Lucene query:
- Never use commas as Lucene operators
- Quote multi-word phrases with double quotes
- Use explicit OR between terms
- Escape Lucene special characters: + - && || ! ( ) { } [ ] ^ " ~ * ? : \\ /
- If a term contains special characters, escape them with backslash

Output strict JSON:
{"expanded_query":"...", "expanded_query_lucene":"..."}"""

        user_prompt = f"Expand this topic: {request.text.strip()}"

        # Check if OpenAI API key is available
        if not OPENAI_API_KEY:
            # Fallback: quote the raw input
            expanded_query = request.text.strip()
            expanded_query_lucene = f'"{request.text.strip()}"'
            return ExpandResponse(
                expanded_query=expanded_query,
                expanded_query_lucene=expanded_query_lucene
            )
        
        # Call GPT-4o using the new OpenAI API format
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )

        # Extract the response content
        content = response.choices[0].message.content.strip()
        
        # Try to parse JSON from the response
        try:
            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                # Fallback: quote the raw input
                expanded_query = request.text.strip()
                expanded_query_lucene = f'"{request.text.strip()}"'
                return ExpandResponse(
                    expanded_query=expanded_query,
                    expanded_query_lucene=expanded_query_lucene
                )
        except json.JSONDecodeError:
            # Fallback: quote the raw input
            expanded_query = request.text.strip()
            expanded_query_lucene = f'"{request.text.strip()}"'
            return ExpandResponse(
                expanded_query=expanded_query,
                expanded_query_lucene=expanded_query_lucene
            )

        # Validate the parsed response
        if not isinstance(parsed, dict):
            raise ValueError("Invalid response format")
        
        expanded_query = parsed.get("expanded_query", "")
        expanded_query_lucene = parsed.get("expanded_query_lucene", "")
        
        if not expanded_query or not expanded_query_lucene:
            # Fallback: quote the raw input
            expanded_query = request.text.strip()
            expanded_query_lucene = f'"{request.text.strip()}"'
        else:
            # Sanitize the Lucene query
            expanded_query_lucene = sanitize_lucene_query(expanded_query_lucene)

        return ExpandResponse(
            expanded_query=expanded_query,
            expanded_query_lucene=expanded_query_lucene
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in query expansion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to expand query: {str(e)}")
