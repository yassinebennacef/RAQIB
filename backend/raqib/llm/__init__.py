"""Optional local LLM (Qwen3-4B via Ollama). It never scores or decides: it only rephrases verified
facts (officer brief) and translates a question into a worklist filter the officer confirms.
Every path has a deterministic fallback (template brief, rule-based parser)."""
