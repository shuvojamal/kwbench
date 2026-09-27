"""
Unified wrapper around OpenAI (GPT), Google Gemini, and Anthropic (Claude).
Each function takes a plain-text prompt and a model name, returns plain text.
Keys are passed in per call (loaded from config.json by app.py) — never hardcoded.
"""
import json
import re


def call_ai(provider: str, api_key: str, prompt: str, model: str = None) -> str:
    provider = (provider or "").lower()
    if provider == "openai":
        return _call_openai(api_key, prompt, model or "gpt-4o-mini")
    if provider == "gemini":
        return _call_gemini(api_key, prompt, model or "gemini-1.5-flash")
    if provider == "claude":
        return _call_claude(api_key, prompt, model or "claude-sonnet-4-6")
    raise ValueError(f"Unknown provider: {provider}")


def _call_openai(api_key, prompt, model):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return resp.choices[0].message.content


def _call_gemini(api_key, prompt, model):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(model)
    resp = m.generate_content(prompt)
    return resp.text


def _call_claude(api_key, prompt, model):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def extract_json(text: str):
    """Pull a JSON array/object out of a model reply that may have extra prose or code fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start_chars, end_chars = "[{", "]}"
    for s_char, e_char in zip(start_chars, end_chars):
        start = text.find(s_char)
        end = text.rfind(e_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("Could not find valid JSON in the model's reply")
