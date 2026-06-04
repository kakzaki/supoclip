from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
import asyncio
import json
import logging
import re

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic import AliasChoices, BaseModel, Field, field_validator

from .config import Config, get_config
from .runtime_settings import apply_settings_to_process_env

logger = logging.getLogger(__name__)

# ── Clip duration presets ────────────────────────────────────────────
# These map user-friendly names (or raw second values) to the internal
# min/ideal/max bounds used by the LLM system prompt and the validation
# / repair logic.


@dataclass(frozen=True)
class ClipDurationConfig:
    min_seconds: int   # hard floor — segments shorter than this are rejected
    ideal_min: int     # soft floor — the LLM is told to prefer above this
    ideal_max: int     # soft ceiling
    max_seconds: int   # hard ceiling
    max_clips: int     # max number of segments to request from the LLM

    @classmethod
    def from_preset(cls, preset: str, max_clips: int = 5) -> "ClipDurationConfig":
        """Resolve a preset name or a raw-seconds string like ``"45"``."""
        preset = preset.strip().lower()
        if preset in DURATION_PRESETS:
            return DURATION_PRESETS[preset].with_max_clips(max_clips)
        # Allow raw seconds: "30" → short, "60" → medium, etc.
        try:
            target = int(preset)
        except ValueError:
            return DURATION_PRESETS["medium"].with_max_clips(max_clips)
        if target <= 20:
            return DURATION_PRESETS["short"].with_max_clips(max_clips)
        if target <= 40:
            return DURATION_PRESETS["medium"].with_max_clips(max_clips)
        return DURATION_PRESETS["long"].with_max_clips(max_clips)

    def with_max_clips(self, max_clips: int) -> "ClipDurationConfig":
        return ClipDurationConfig(
            min_seconds=self.min_seconds,
            ideal_min=self.ideal_min,
            ideal_max=self.ideal_max,
            max_seconds=self.max_seconds,
            max_clips=max_clips,
        )


DURATION_PRESETS: dict[str, ClipDurationConfig] = {
    "short": ClipDurationConfig(
        min_seconds=10, ideal_min=15, ideal_max=30, max_seconds=35, max_clips=5,
    ),
    "medium": ClipDurationConfig(
        min_seconds=20, ideal_min=25, ideal_max=50, max_seconds=60, max_clips=5,
    ),
    "long": ClipDurationConfig(
        min_seconds=30, ideal_min=45, ideal_max=90, max_seconds=120, max_clips=5,
    ),
}

# Default (backward-compatible with old hardcoded constants).
_dc = DURATION_PRESETS["medium"]
IDEAL_CLIP_MIN_SECONDS = _dc.ideal_min
IDEAL_CLIP_MAX_SECONDS = _dc.ideal_max
MIN_ACCEPTED_CLIP_SECONDS = _dc.min_seconds
MAX_ACCEPTED_CLIP_SECONDS = _dc.max_seconds

TRANSCRIPT_ANALYSIS_CACHE_VERSION = "longer-clips-v3-duration-repair"
TRANSCRIPT_SPAN_RE = re.compile(
    r"^\[(?P<start>\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<text>.*)$"
)


class ViralityAnalysis(BaseModel):
    """Detailed virality breakdown for a segment."""

    hook_score: int = Field(
        default=15,
        description="How strong is the opening hook (0-25)",
        ge=0,
        le=25,
    )
    engagement_score: int = Field(
        default=15,
        description="How engaging/entertaining is the content (0-25)",
        ge=0,
        le=25,
    )
    value_score: int = Field(
        default=15,
        description="Educational/informational value (0-25)",
        ge=0,
        le=25,
    )
    shareability_score: int = Field(
        default=15,
        description="Likelihood of being shared (0-25)",
        ge=0,
        le=25,
    )
    total_score: int = Field(
        default=60,
        description="Combined virality score (0-100)",
        ge=0,
        le=100,
    )
    hook_type: Optional[
        Literal["question", "statement", "statistic", "story", "contrast", "none"]
    ] = Field(
        default="none",
        description="Type of hook: question, statement, statistic, story, contrast, or none",
    )
    virality_reasoning: str = Field(
        default="The model did not provide a detailed virality breakdown.",
        description="Explanation of the virality score",
    )
    # ── Qualitative insights (new) ─────────────────────────────────
    best_platform: Optional[str] = Field(
        default=None,
        description=(
            "Recommended platform for this clip: 'TikTok', 'YouTube Shorts', "
            "'Instagram Reels', or 'All platforms'"
        ),
    )
    target_audience: Optional[str] = Field(
        default=None,
        description=(
            "Who this clip would resonate with (e.g. 'Aspiring entrepreneurs', "
            "'Gen Z travelers', 'Busy parents'). 1-2 sentences max."
        ),
    )
    suggested_title: Optional[str] = Field(
        default=None,
        description=(
            "A clickable, curiosity-driven title for this clip (max 80 chars). "
            "Should feel native to the recommended platform."
        ),
    )
    suggested_caption: Optional[str] = Field(
        default=None,
        description=(
            "A ready-to-post social media caption for this clip. "
            "Include a compelling 1-2 sentence description, 3-5 relevant emojis, "
            "and 3-5 hashtags (e.g. '#motivation #entrepreneurship'). "
            "Keep it under 250 chars. Should feel native and not overly salesy."
        ),
    )
    weakness_flag: Optional[str] = Field(
        default=None,
        description=(
            "What might hold this clip back (e.g. 'Hook takes 3 seconds too long', "
            "'Punchline is buried mid-clip', 'Needs more visual variety'). "
            "If none, say 'No major weakness'."
        ),
    )


def _default_virality_analysis() -> ViralityAnalysis:
    return ViralityAnalysis()


class TranscriptSegment(BaseModel):
    """Represents a relevant segment of transcript with precise timing and virality analysis."""

    start_time: str = Field(description="Start timestamp in MM:SS format")
    end_time: str = Field(description="End timestamp in MM:SS format")
    text: str = Field(
        validation_alias=AliasChoices("text", "segment"),
        description=(
            "Transcript text taken only from the selected timestamp range. "
            "Keep it verbatim or near-verbatim, and do not paraphrase or merge non-contiguous lines."
        )
    )
    relevance_score: float = Field(
        default=0.75,
        description="Relevance score from 0.0 to 1.0", ge=0.0, le=1.0
    )
    reasoning: str = Field(
        default="Selected by the AI model as a clip candidate.",
        description=(
            "Brief factual explanation of why this exact segment works as a clip. "
            "Base it only on the provided transcript content."
        )
    )
    virality: ViralityAnalysis = Field(
        default_factory=_default_virality_analysis,
        description="Detailed virality score breakdown",
    )

    @field_validator("relevance_score", mode="before")
    @classmethod
    def _coerce_percent_relevance_score(cls, value: Any) -> Any:
        if value is None:
            return value
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return value
        if numeric_value > 1 and numeric_value <= 100:
            return numeric_value / 100
        return value


class BRollOpportunity(BaseModel):
    """Identifies an opportunity to insert B-roll footage."""

    timestamp: str = Field(
        default="00:00",
        validation_alias=AliasChoices("timestamp", "segment_start_time", "start_time"),
        description="When to insert B-roll (MM:SS format)",
    )
    duration: float = Field(
        default=3.0,
        description="How long to show B-roll (2-5 seconds)",
        ge=2.0,
        le=5.0,
    )
    search_term: str = Field(
        default="related visual",
        validation_alias=AliasChoices("search_term", "broll", "visual", "query"),
        description="Keyword to search for B-roll footage",
    )
    context: str = Field(
        default="Suggested B-roll opportunity from the model.",
        validation_alias=AliasChoices("context", "description"),
        description="What's being discussed at this point",
    )

    @field_validator("search_term", "context", mode="before")
    @classmethod
    def _coerce_textish_value(cls, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item is not None)
        return str(value)


class TranscriptAnalysis(BaseModel):
    """Analysis result for transcript segments with virality and B-roll opportunities."""

    most_relevant_segments: List[TranscriptSegment]
    summary: str = Field(description="Brief summary of the video content")
    key_topics: List[str] = Field(description="List of main topics discussed")
    broll_opportunities: Optional[List[BRollOpportunity]] = Field(
        default=None, description="Opportunities to insert B-roll footage"
    )


def _build_duration_section(dc: ClipDurationConfig) -> str:
    """Build the TIMING GUIDELINES + TIMESTAMP REQUIREMENTS sections dynamically."""
    return f"""TIMING GUIDELINES:
- Target {dc.ideal_min}-{dc.ideal_max} seconds for most clips
- Use {dc.min_seconds}-{dc.ideal_min - 1} seconds only when the moment is exceptionally dense, self-contained, and complete
- CRITICAL: start_time MUST be different from end_time (minimum {dc.min_seconds} seconds apart)
- Focus on natural content boundaries rather than arbitrary time limits
- Include enough context for the segment to be understandable
- Prefer roughly {dc.ideal_min}-{dc.ideal_max} seconds when possible
- Start at the hook or the minimum setup needed to make the hook land, and end after the payoff
- If a highlight is only one good line, expand to include the surrounding setup and payoff rather than returning a tiny fragment
- Stop expanding when the topic drifts, the speaker repeats the same point, or the clip loses momentum

TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT:
- Use EXACT timestamps as they appear in the transcript
- Never modify timestamp format (keep MM:SS structure)
- start_time MUST be LESS THAN end_time (start_time < end_time)
- MINIMUM segment duration: {dc.min_seconds} seconds (end_time - start_time >= {dc.min_seconds} seconds)
- IDEAL segment duration: {dc.ideal_min}-{dc.ideal_max} seconds
- MAXIMUM segment duration: {dc.max_seconds} seconds
- Look at transcript ranges like [02:25 - 02:35] and use different start/end times
- NEVER use the same timestamp for both start_time and end_time
- Example: start_time: "02:25", end_time: "02:35" (NOT "02:25" and "02:25")"""


def _build_transcript_analysis_system_prompt(dc: ClipDurationConfig) -> str:
    """Build the system prompt with duration-specific timing instructions."""
    duration_section = _build_duration_section(dc)
    clip_count = f"Choose {dc.max_clips - 2}-{dc.max_clips} segments total" if dc.max_clips > 3 else f"Choose 2-{dc.max_clips} segments total"

    return f"""You are an expert transcript analyst for short-form video editing.

Your job is extraction and ranking, not creative rewriting. You must stay fully grounded in the transcript and choose the best clip candidates that already exist in the source material.

OUTPUT CONTRACT:
- Return valid JSON only. Do not output Markdown, headings, bullets, prose, code fences, explanations, or commentary outside the JSON object.
- The top-level JSON object must include: "most_relevant_segments", "summary", and "key_topics".
- Only include "broll_opportunities" when B-roll was requested.
- Each item in "most_relevant_segments" must include: "start_time", "end_time", "text", "relevance_score", "reasoning", and "virality".
- Do not use "segment" as an output field. Use "text".
- "virality" must include: "hook_score", "engagement_score", "value_score", "shareability_score", "total_score", "hook_type", "virality_reasoning", "best_platform", "target_audience", "suggested_title", "suggested_caption", and "weakness_flag".
- Every returned segment must be {dc.min_seconds}-{dc.max_seconds} seconds long. Prefer {dc.ideal_min}-{dc.ideal_max} seconds.

CORE OBJECTIVES:
1. Identify segments that would be compelling on social media platforms
2. Focus on complete thoughts, insights, or entertaining moments
3. Prioritize content with hooks, emotional moments, or valuable information
4. Each segment should be engaging and worth watching
5. Score each segment's viral potential with detailed breakdown

GROUNDING RULES:
1. Use only the provided transcript lines and timestamps
2. Never invent facts, tone, context, or transitions that are not present
3. Treat this as span selection over a timestamped transcript, not open-ended summarization
4. Each selected segment must map to one contiguous range in the transcript
5. segment.text must match the chosen span closely and must not include content from outside the chosen range
6. Do not stitch together distant moments into one clip
7. If a speaker label appears, use it only if it is part of the spoken content and helps clarity

CONTENT NEUTRALITY RULES:
1. This is clipping software for legitimate editing workflows
2. Do not judge, moralize, or downgrade a segment just because the topic is controversial, sensitive, adult, political, criminal, medical, or otherwise intense
3. Evaluate segments only on clip quality: clarity, self-contained value, hook strength, emotional impact, specificity, and shareability
4. Do not refuse analysis just because the speaker describes risky, offensive, or uncomfortable subject matter
5. Only downgrade a segment when the transcript itself is weak, confusing, repetitive, unusable, or a poor standalone clip

SEGMENT SELECTION CRITERIA:
1. STRONG HOOKS: Attention-grabbing opening lines
2. VALUABLE CONTENT: Tips, insights, interesting facts, stories
3. EMOTIONAL MOMENTS: Excitement, surprise, humor, inspiration
4. COMPLETE THOUGHTS: Self-contained ideas that make sense alone
5. ENTERTAINING: Content people would want to share
6. HIGH SIGNAL: Prefer specific, concrete language over vague discussion
7. LOW FILLER: Avoid greetings, sponsor reads, repeated setup, throat-clearing, and housekeeping unless they are unusually compelling

WHAT A GOOD CLIP FEELS LIKE:
- A viewer should understand and care without the original title, thumbnail, or previous context
- Prefer a complete mini-story or argument: setup, tension or claim, specific detail, and payoff
- Expand a great short moment to nearby contiguous lines when that adds needed setup, stakes, or payoff
- Strong picks include contrarian claims, mistakes or lessons, concrete examples, before/after moments, frameworks, surprising results, emotionally charged reactions, and complete answers to interesting questions
- Bad picks include intros, sponsor or CTA sections, vague setup, contextless quote fragments, repeated points, definitions without payoff, meandering background, and answer fragments that require unseen context

VIRALITY SCORING (0-100 total, from four 0-25 subscores):
For each segment, provide a detailed virality breakdown:

1. HOOK STRENGTH (0-25):
   - 20-25: Immediately grabs attention (surprising fact, bold claim, intriguing question)
   - 15-19: Good opener that creates curiosity
   - 10-14: Decent start but could be stronger
   - 0-9: Weak or no hook

2. ENGAGEMENT (0-25):
   - 20-25: Highly entertaining, emotional, or dramatic
   - 15-19: Interesting and holds attention
   - 10-14: Moderately engaging
   - 0-9: Flat or boring delivery

3. VALUE (0-25):
   - 20-25: Actionable insights, unique knowledge, or transformative ideas
   - 15-19: Useful information most people don't know
   - 10-14: Somewhat informative
   - 0-9: Common knowledge or filler content

4. SHAREABILITY (0-25):
   - 20-25: "I need to send this to someone" content
   - 15-19: Content worth bookmarking
   - 10-14: Nice but not share-worthy
   - 0-9: Generic content

HOOK TYPES to identify:
- "question": Opens with a question that creates curiosity
- "statement": Bold claim or surprising statement
- "statistic": Uses compelling numbers or data
- "story": Starts with narrative/anecdote
- "contrast": Before/after or problem/solution framing
- "none": No clear hook pattern

QUALITATIVE INSIGHTS (provide for every segment):
1. best_platform: Which platform this clip is best suited for.
   - "TikTok" — fast-paced, leans toward entertainment/fun, under 30s ideal
   - "YouTube Shorts" — informational/educational punch, works well 30-50s
   - "Instagram Reels" — polished, aesthetic, lifestyle-focused
   - "All platforms" — universal appeal, works everywhere
2. target_audience: Who this clip would resonate with (1-2 sentences).
   Be specific rather than generic (e.g. "Freelance designers struggling with pricing" not "People interested in design").
3. suggested_title: A clickable, curiosity-driven title for this clip (max 80 chars).
   Make it native to the recommended platform. Examples:
   - "The pricing mistake 90% of freelancers make 💸"
   - "I tried waking up at 4am for 30 days. Here's what happened"
4. suggested_caption: A ready-to-post social media caption. Include:
   - 1-2 sentence compelling description that teases the content
   - 3-5 relevant emojis scattered naturally
   - 3-5 hashtags at the end (e.g. "#motivation #entrepreneurship")
   Keep it under 250 chars, natural tone, not salesy. Example:
   "This shift changed everything for me 💡 Stop trading time for money and start building systems that work while you sleep. 🚀 #passiveincome #businesstips #entrepreneur"
5. weakness_flag: What might hold this clip back. Be honest and specific.
   - Examples: "Hook takes 3 seconds too long to get to the point", "Payoff is expected/cliché", "Middle section loses momentum", "Needs visual variety — 20 seconds of talking head"
   - If the clip is solid across all dimensions, say "No major weakness".

B-ROLL OPPORTUNITIES:
Identify 2-4 moments in each segment where B-roll footage could enhance the video:
- When specific objects, places, or concepts are mentioned
- During explanations that could benefit from visual illustration
- At emotional peaks that could use supporting imagery
- Use simple, searchable keywords (e.g., "coffee shop", "laptop coding", "money stack")

{duration_section}

SCORING AND OUTPUT RULES:
- relevance_score should reflect how well the segment works as a standalone short clip, not just whether the topic is generally important
- Penalize clips that are only quotable but not self-contained, too generic, missing setup, missing payoff, or padded with filler
- virality_reasoning and reasoning should cite what is actually present in the chosen span
- summary and key_topics must also stay grounded in the transcript and should not add outside interpretation

{clip_count}. Quality over quantity: choose fewer stronger segments over filling a quota. Every selected segment must be accurate, self-contained, have proper time ranges, and score high on virality metrics."""

# Lazy-loaded agent to avoid import-time failures when API keys aren't set
_transcript_agent: Optional[Agent[None, TranscriptAnalysis]] = None
_transcript_agent_signature: Optional[tuple[str | None, ...]] = None

SUPPORTED_LLM_PROVIDERS = {"google", "google-gla", "openai", "anthropic", "ollama", "groq", "deepseek"}


def _split_llm_name(model_name: str) -> tuple[str, str | None]:
    if ":" not in model_name:
        return model_name.strip().lower(), None

    provider, provider_model_name = model_name.split(":", 1)
    return provider.strip().lower(), provider_model_name.strip() or None


def _get_missing_llm_key_error(model_name: str, runtime_config: Config) -> Optional[str]:
    """Return a clear configuration error when the selected LLM key is missing."""
    provider, provider_model_name = _split_llm_name(model_name)

    if provider not in SUPPORTED_LLM_PROVIDERS:
        return (
            f"Unsupported LLM provider '{provider}'. "
            "Use google-gla:*, openai:*, anthropic:*, ollama:*, groq:*, or deepseek:*."
        )

    if not provider_model_name:
        return (
            "Selected LLM is missing a model name. "
            "Use the format provider:model, for example ollama:gpt-oss:20b."
        )

    if provider in {"google", "google-gla"} and not runtime_config.google_api_key:
        return (
            "Selected LLM provider is Google, but GOOGLE_API_KEY is not set. "
            "Set GOOGLE_API_KEY or set LLM to openai:* / anthropic:* / ollama:* / groq:* with the matching API key."
        )

    if provider == "openai" and not runtime_config.openai_api_key:
        return (
            "Selected LLM provider is OpenAI, but OPENAI_API_KEY is not set. "
            "Set OPENAI_API_KEY or choose another provider with a matching API key."
        )

    if provider == "anthropic" and not runtime_config.anthropic_api_key:
        return (
            "Selected LLM provider is Anthropic, but ANTHROPIC_API_KEY is not set. "
            "Set ANTHROPIC_API_KEY or choose another provider with a matching API key."
        )

    if provider == "groq" and not runtime_config.groq_api_key:
        return (
            "Selected LLM provider is Groq, but GROQ_API_KEY is not set. "
            "Set GROQ_API_KEY or choose another provider with a matching API key."
        )

    if provider == "deepseek" and not runtime_config.deepseek_api_key:
        return (
            "Selected LLM provider is DeepSeek, but DEEPSEEK_API_KEY is not set. "
            "Set DEEPSEEK_API_KEY or choose another provider with a matching API key."
        )

    if provider == "ollama":
        # Ollama can run locally without an API key. OLLAMA_BASE_URL/OLLAMA_API_KEY
        # are optional and passed through as environment variables.
        return None

    return None


def _inline_json_schema_refs(schema: dict) -> dict:
    """Recursively inline all ``$ref`` references in a JSON Schema.

    DeepSeek (and some other OpenAI-compatible providers) do not support
    ``$ref`` / ``$defs`` inside function-calling parameter schemas.  When a
    model like ``TranscriptAnalysis`` contains nested models (e.g.
    ``TranscriptSegment.virality`` → ``ViralityAnalysis``), pydantic-ai
    generates a schema with ``$ref`` entries that DeepSeek silently rejects
    by returning an empty ``{}`` tool-call argument.

    This helper fully resolves every ``$ref`` against its corresponding
    ``$defs`` entry, producing a flat, self-contained schema with zero
    references.
    """
    defs = schema.get("$defs", {})

    def _walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                if ref.startswith("#/$defs/") and not node.keys() - {"$ref"}:
                    # Pure reference — fully replace with inlined definition.
                    key = ref[len("#/$defs/"):]
                    if key in defs:
                        return _walk(json.loads(json.dumps(defs[key])))
                elif ref.startswith("#/$defs/"):
                    # Reference with sibling keys (e.g. description) —
                    # inline the definition and merge siblings on top.
                    key = ref[len("#/$defs/"):]
                    if key in defs:
                        resolved = json.loads(json.dumps(defs[key]))
                        siblings = {k: v for k, v in node.items() if k != "$ref"}
                        merged = _walk(resolved)
                        merged.update(siblings)
                        return merged
                return node
            return {k: _walk(v) for k, v in node.items()}
        elif isinstance(node, list):
            return [_walk(item) for item in node]
        return node

    return _walk(json.loads(json.dumps(schema)))


def _build_transcript_model(runtime_config: Config) -> Model | str:
    provider, provider_model_name = _split_llm_name(runtime_config.llm)

    # DeepSeek API is OpenAI-compatible but pydantic-ai has no native
    # DeepSeek provider.  Build an OpenAIModel pointed at api.deepseek.com
    # so tool calling (and therefore structured output) works correctly.
    if provider == "deepseek":
        if not runtime_config.deepseek_api_key:
            raise RuntimeError(
                "DeepSeek LLM selected but DEEPSEEK_API_KEY is not set. "
                "Set DEEPSEEK_API_KEY or choose another provider "
                "(google-gla:*, openai:*, anthropic:*, etc.)."
            )
        return OpenAIModel(
            provider_model_name or "deepseek-chat",
            provider=OpenAIProvider(
                base_url="https://api.deepseek.com",
                api_key=runtime_config.deepseek_api_key,
            ),
        )

    if provider != "ollama":
        return runtime_config.llm

    if not provider_model_name:
        raise RuntimeError(
            "Selected LLM provider is Ollama, but no model name was provided. "
            "Use the format ollama:<model>, for example ollama:gpt-oss:20b."
        )

    return OllamaModel(
        provider_model_name,
        provider=OllamaProvider(
            base_url=runtime_config.resolve_ollama_base_url(),
            api_key=runtime_config.ollama_api_key,
        ),
    )


def get_transcript_agent(
    duration_config: Optional[ClipDurationConfig] = None,
) -> Agent[None, TranscriptAnalysis]:
    """Get or create the transcript analysis agent (lazy initialization).

    When *duration_config* is provided and differs from the previously cached
    config, the agent is rebuilt with updated timing instructions so the LLM
    respects the user's clip-duration preference.
    """
    global _transcript_agent, _transcript_agent_signature
    runtime_config = get_config()
    provider, _ = _split_llm_name(runtime_config.llm)
    dc = duration_config or ClipDurationConfig.from_preset("medium")
    signature = (
        runtime_config.llm,
        runtime_config.openai_api_key,
        runtime_config.google_api_key,
        runtime_config.anthropic_api_key,
        runtime_config.groq_api_key,
        runtime_config.deepseek_api_key,
        runtime_config.ollama_base_url,
        runtime_config.ollama_api_key,
        dc.min_seconds,
        dc.ideal_min,
        dc.ideal_max,
        dc.max_seconds,
    )
    if _transcript_agent is None or _transcript_agent_signature != signature:
        apply_settings_to_process_env(runtime_config.as_runtime_settings())
        config_error = _get_missing_llm_key_error(runtime_config.llm, runtime_config)
        if config_error:
            raise RuntimeError(config_error)

        _transcript_agent = Agent[None, TranscriptAnalysis](
            model=_build_transcript_model(runtime_config),
            output_type=TranscriptAnalysis,
            system_prompt=_build_transcript_analysis_system_prompt(dc),
            # Some local Ollama/OpenAI-compatible endpoints can return formatted
            # prose before settling on schema-valid JSON. Keep retries limited
            # while still allowing enough repair attempts for local models.
            output_retries=2 if provider == "ollama" else 2,
        )
        _transcript_agent_signature = signature
    return _transcript_agent


def build_transcript_analysis_prompt(
    transcript: str,
    include_broll: bool = False,
    clip_signals: str | None = None,
    duration_config: Optional[ClipDurationConfig] = None,
) -> str:
    """Build the grounded task prompt for transcript analysis."""
    dc = duration_config or ClipDurationConfig.from_preset("medium")
    broll_instruction = ""
    if include_broll:
        broll_instruction = (
            "\n5. Also identify B-roll opportunities for each chosen segment where stock footage could enhance the visual appeal."
        )
    signal_section = ""
    if clip_signals:
        signal_section = (
            "\n\nAdditional deterministic signals from transcript/audio analysis:\n"
            f"{clip_signals}\n\n"
            "Use these as hints only. They should influence ranking, but every final segment "
            "must still be a coherent contiguous transcript range."
        )

    clip_count = f"Choose {dc.max_clips - 2}-{dc.max_clips} segments total" if dc.max_clips > 3 else f"Choose 2-{dc.max_clips} segments total"

    return f"""Analyze this video transcript and identify the most engaging segments for short-form content.

The transcript is formatted as one line per timestamped span, for example:
[00:12 - 00:21] Spoken text here
[00:21 - 00:35] More spoken text here

Follow this workflow:
1. Read the transcript as a sequence of timestamped spans.
2. Select only contiguous ranges that already exist in the transcript.
3. Prefer moments with a strong hook, clear payoff, emotional charge, or concrete value.
4. For each chosen segment, use the earliest timestamp in the selected range as start_time and the latest timestamp in the selected range as end_time.{broll_instruction}

Selection target:
- {clip_count}.
- Most selected clips should be {dc.ideal_min}-{dc.ideal_max} seconds.
- Only choose a {dc.min_seconds}-{dc.ideal_min - 1} second clip when it already contains a full setup and payoff.
- If a strong moment is shorter than {dc.ideal_min} seconds, first try expanding to nearby contiguous transcript lines that add useful context.
- Skip weak standalone picks: intros, sponsor reads, CTAs, contextless quotes, repeated points, vague setup, and answer fragments that require prior context.
- Before returning a segment, ask whether a viewer would understand and care without seeing the rest of the source video.

Critical accuracy requirements:
- Do not fabricate or embellish content.
- Do not use timestamps that are not present in the transcript.
- Do not merge separate non-contiguous moments into one segment.
- segment.text must reflect only the spoken content inside the selected time range.
- If a span lacks enough context to stand alone, expand to nearby contiguous lines rather than guessing.
- If there is a tradeoff between "viral" and "accurate", choose accuracy.
- Do not reject or penalize a segment simply because of the subject matter; stay content-neutral and assess clip quality only.
{signal_section}

JSON-only output requirements:
- Return one valid JSON object and nothing else.
- No Markdown, headings, bullets, code fences, or explanatory text outside JSON.
- Top-level keys: "most_relevant_segments", "summary", "key_topics"{', "broll_opportunities"' if include_broll else ''}.
- Segment keys: "start_time", "end_time", "text", "relevance_score", "reasoning", "virality".
- Virality keys: "hook_score", "engagement_score", "value_score", "shareability_score", "total_score", "hook_type", "virality_reasoning", "best_platform", "target_audience", "suggested_title", "weakness_flag".
- Do not return segments shorter than {dc.min_seconds} seconds or longer than {dc.max_seconds} seconds.

Transcript:
{transcript}"""


def _parse_transcript_timestamp_seconds(timestamp: str) -> int:
    """Parse MM:SS or HH:MM:SS transcript timestamps into seconds."""
    parts = [int(part) for part in timestamp.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    raise ValueError(f"Unsupported timestamp format: {timestamp}")


def _format_transcript_timestamp(seconds: int) -> str:
    """Format seconds as a transcript timestamp."""
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _parse_transcript_spans(transcript: str) -> list[dict[str, Any]]:
    """Parse timestamped transcript lines into spans."""
    spans = []
    for line in transcript.splitlines():
        match = TRANSCRIPT_SPAN_RE.match(line.strip())
        if not match:
            continue
        try:
            start_seconds = _parse_transcript_timestamp_seconds(match.group("start"))
            end_seconds = _parse_transcript_timestamp_seconds(match.group("end"))
        except ValueError:
            continue
        if end_seconds <= start_seconds:
            continue
        spans.append(
            {
                "start": start_seconds,
                "end": end_seconds,
                "text": match.group("text").strip(),
            }
        )
    return spans


def _extract_transcript_text(
    transcript_spans: list[dict[str, Any]], start_seconds: int, end_seconds: int
) -> str:
    """Return transcript text overlapping a selected time range."""
    selected_text = [
        span["text"]
        for span in transcript_spans
        if span["text"]
        and span["end"] > start_seconds
        and span["start"] < end_seconds
    ]
    return " ".join(selected_text).strip()


def _choose_repaired_bounds(
    transcript_spans: list[dict[str, Any]], start_seconds: int, end_seconds: int
) -> tuple[int, int] | None:
    """Repair model-selected bounds to the nearest acceptable contiguous range."""
    if not transcript_spans:
        return None

    starts = sorted({span["start"] for span in transcript_spans})
    ends = sorted({span["end"] for span in transcript_spans})
    current_duration = end_seconds - start_seconds

    if current_duration > MAX_ACCEPTED_CLIP_SECONDS:
        target_end = start_seconds + IDEAL_CLIP_MAX_SECONDS
        candidate_ends = [
            candidate
            for candidate in ends
            if start_seconds + MIN_ACCEPTED_CLIP_SECONDS
            <= candidate
            <= min(target_end, end_seconds)
        ]
        if candidate_ends:
            return start_seconds, max(candidate_ends)
        if start_seconds + MIN_ACCEPTED_CLIP_SECONDS <= target_end:
            return start_seconds, target_end
        return None

    if current_duration < MIN_ACCEPTED_CLIP_SECONDS:
        candidate_ranges: list[tuple[int, int, int]] = []
        for candidate_start in starts:
            if candidate_start > start_seconds:
                continue
            for candidate_end in ends:
                if candidate_end < end_seconds:
                    continue
                duration = candidate_end - candidate_start
                if MIN_ACCEPTED_CLIP_SECONDS <= duration <= MAX_ACCEPTED_CLIP_SECONDS:
                    extra_context = (start_seconds - candidate_start) + (
                        candidate_end - end_seconds
                    )
                    ideal_penalty = 0
                    if duration < IDEAL_CLIP_MIN_SECONDS:
                        ideal_penalty = IDEAL_CLIP_MIN_SECONDS - duration
                    elif duration > IDEAL_CLIP_MAX_SECONDS:
                        ideal_penalty = duration - IDEAL_CLIP_MAX_SECONDS
                    candidate_ranges.append(
                        (ideal_penalty * 1000 + extra_context, candidate_start, candidate_end)
                    )
        if candidate_ranges:
            _, repaired_start, repaired_end = min(candidate_ranges)
            return repaired_start, repaired_end

    return None


def _repair_segment_bounds(
    segment: TranscriptSegment,
    transcript_spans: list[dict[str, Any]],
    start_seconds: int,
    end_seconds: int,
) -> tuple[int, int] | None:
    """Adjust near-miss model ranges to usable transcript-aligned bounds."""
    repaired_bounds = _choose_repaired_bounds(
        transcript_spans,
        start_seconds,
        end_seconds,
    )
    if not repaired_bounds:
        return None

    repaired_start, repaired_end = repaired_bounds
    segment.start_time = _format_transcript_timestamp(repaired_start)
    segment.end_time = _format_transcript_timestamp(repaired_end)
    repaired_text = _extract_transcript_text(
        transcript_spans,
        repaired_start,
        repaired_end,
    )
    if repaired_text:
        segment.text = repaired_text
    logger.info(
        "Repaired segment duration: %s-%s -> %s-%s",
        _format_transcript_timestamp(start_seconds),
        _format_transcript_timestamp(end_seconds),
        segment.start_time,
        segment.end_time,
    )
    return repaired_start, repaired_end


# Approx 32k chars ≈ 8k tokens, safe for Groq's free tier (12k TPM).
# Leave headroom for the system prompt, JSON output, and instruction text.
_MAX_TRANSCRIPT_CHARS_FOR_LOW_TPM = 30_000


def _should_limit_transcript_tokens() -> bool:
    """Check whether the current LLM provider has a known low TPM limit."""
    runtime_config = get_config()
    provider, _ = _split_llm_name(runtime_config.llm)
    return provider == "groq"


def _truncate_transcript(transcript: str) -> str:
    """Truncate long transcripts to stay within low TPM provider limits.

    Uses stratified sampling across the full video timeline instead of
    cutting from the top, so the LLM sees content from the beginning,
    middle, and end rather than only the first few minutes.
    """
    if not _should_limit_transcript_tokens():
        return transcript

    if len(transcript) <= _MAX_TRANSCRIPT_CHARS_FOR_LOW_TPM:
        return transcript

    lines = transcript.splitlines()
    if not lines:
        return transcript

    # Edge case: first line alone exceeds the limit; take a raw slice.
    if len(lines[0]) > _MAX_TRANSCRIPT_CHARS_FOR_LOW_TPM:
        return transcript[:_MAX_TRANSCRIPT_CHARS_FOR_LOW_TPM]

    # Parse timestamps so we can stratify by time rather than by line count.
    parsed: list[dict[str, Any]] = []
    for line in lines:
        match = TRANSCRIPT_SPAN_RE.match(line.strip())
        if match:
            try:
                parsed.append({
                    "line": line,
                    "start_s": _parse_transcript_timestamp_seconds(match.group("start")),
                })
                continue
            except ValueError:
                pass
        parsed.append({"line": line, "start_s": None})

    if not parsed:
        return transcript

    # Find the time range so we can create equal-duration strata.
    timestamps = [p["start_s"] for p in parsed if p["start_s"] is not None]
    if not timestamps:
        # No parseable timestamps; uniform sample by line index.
        step = max(1, len(lines) // max(1, _MAX_TRANSCRIPT_CHARS_FOR_LOW_TPM // 80))
        sampled: list[str] = []
        total = 0
        for i in range(0, len(lines), step):
            if total + len(lines[i]) > _MAX_TRANSCRIPT_CHARS_FOR_LOW_TPM:
                break
            sampled.append(lines[i])
            total += len(lines[i]) + 1
        if not sampled:
            return transcript[:_MAX_TRANSCRIPT_CHARS_FOR_LOW_TPM]
        logger.warning(
            "Transcript sampled uniformly from %d to %d chars (%d/%d lines).",
            len(transcript),
            total,
            len(sampled),
            len(lines),
        )
        return "\n".join(sampled)

    min_time, max_time = min(timestamps), max(timestamps)
    total_duration = max(1.0, max_time - min_time)

    # Create 6 equal-duration strata and pick lines proportionally from each.
    num_strata = 6
    stratum_budget = _MAX_TRANSCRIPT_CHARS_FOR_LOW_TPM // num_strata
    stratum_lines: dict[int, list[str]] = {s: [] for s in range(num_strata)}

    for entry in parsed:
        if entry["start_s"] is not None:
            fraction = (entry["start_s"] - min_time) / total_duration
            stratum = min(num_strata - 1, int(fraction * num_strata))
        else:
            stratum = 0
        line_len = len(entry["line"]) + 1
        current_total = sum(len(l) + 1 for l in stratum_lines[stratum])
        if current_total + line_len <= stratum_budget:
            stratum_lines[stratum].append(entry["line"])

    # Assemble in stratum order so the LLM sees a chronological summary.
    truncated_lines: list[str] = []
    total = 0
    for s in range(num_strata):
        for line in stratum_lines[s]:
            if total + len(line) > _MAX_TRANSCRIPT_CHARS_FOR_LOW_TPM:
                break
            truncated_lines.append(line)
            total += len(line) + 1

    if not truncated_lines:
        return transcript[:_MAX_TRANSCRIPT_CHARS_FOR_LOW_TPM]

    # Add a visible stratum marker so the LLM knows it's seeing a time-stratified sample.
    header = (
        f"[Note: transcript truncated from {len(transcript)} chars to fit limits. "
        f"Lines are sampled proportionally from {num_strata} time strata across "
        f"{int(total_duration // 60)}m{int(total_duration % 60)}s of content.]"
    )
    logger.warning(
        "Transcript stratified from %d to %d chars across %d strata.",
        len(transcript),
        total + len(header),
        num_strata,
    )
    return header + "\n" + "\n".join(truncated_lines)


def _filter_segment_diversity(
    segments: list[TranscriptSegment],
    min_time_gap_fraction: float = 0.08,
    min_text_jaccard: float = 0.45,
) -> list[TranscriptSegment]:
    """Remove segments that are too close in time or too similar in text.

    When two segments overlap in time by more than *min_time_gap_fraction*
    of the source duration, or share more than *min_text_jaccard* fraction
    of unique words, the lower-scoring one is dropped.

    Segments are assumed to be pre-sorted by score (best first).
    """
    if len(segments) <= 1:
        return segments

    # Compute the total time span of all segments to scale the gap threshold.
    all_starts: list[int] = []
    all_ends: list[int] = []
    for seg in segments:
        try:
            all_starts.append(_parse_transcript_timestamp_seconds(seg.start_time))
            all_ends.append(_parse_transcript_timestamp_seconds(seg.end_time))
        except ValueError:
            continue
    source_span = (max(all_ends) - min(all_starts)) if all_starts else 300
    min_gap_seconds = max(8.0, source_span * min_time_gap_fraction)

    def _word_set(text: str) -> set[str]:
        return set(re.findall(r"[a-zA-Z0-9']+", text.lower()))

    kept: list[TranscriptSegment] = []
    kept_word_sets: list[set[str]] = []

    for segment in segments:
        try:
            seg_start = _parse_transcript_timestamp_seconds(segment.start_time)
            seg_end = _parse_transcript_timestamp_seconds(segment.end_time)
        except ValueError:
            kept.append(segment)
            kept_word_sets.append(_word_set(segment.text))
            continue

        seg_words = _word_set(segment.text)
        if not seg_words:
            kept.append(segment)
            kept_word_sets.append(seg_words)
            continue

        too_close = False
        for k_idx, (k_seg, k_words) in enumerate(zip(kept, kept_word_sets)):
            try:
                k_start = _parse_transcript_timestamp_seconds(k_seg.start_time)
                k_end = _parse_transcript_timestamp_seconds(k_seg.end_time)
            except ValueError:
                continue

            # Time proximity check: overlapping or too close
            gap = max(0.0, max(k_start, seg_start) - min(k_end, seg_end))
            if gap < min_gap_seconds and abs(seg_start - k_start) < min_gap_seconds * 3:
                too_close = True
                logger.info(
                    "Diversity: dropping '%s' (too close in time to '%s')",
                    segment.text[:60],
                    k_seg.text[:60],
                )
                break

            # Text similarity check (Jaccard)
            if k_words:
                intersection = len(seg_words & k_words)
                union = len(seg_words | k_words)
                jaccard = intersection / union if union > 0 else 0.0
                if jaccard > min_text_jaccard:
                    too_close = True
                    logger.info(
                        "Diversity: dropping '%s' (%.0f%% word overlap with '%s')",
                        segment.text[:60],
                        jaccard * 100,
                        k_seg.text[:60],
                    )
                    break

        if not too_close:
            kept.append(segment)
            kept_word_sets.append(seg_words)

    dropped = len(segments) - len(kept)
    if dropped:
        logger.info("Diversity filter dropped %d near-duplicate segment(s).", dropped)
    return kept


async def _run_deepseek_analysis(
    transcript: str,
    include_broll: bool = False,
    clip_signals: str | None = None,
    duration_config: Optional[ClipDurationConfig] = None,
) -> TranscriptAnalysis:
    """Run transcript analysis on DeepSeek using plain JSON mode.

    DeepSeek's API does not support ``$ref`` / ``$defs`` inside function-calling
    parameter schemas, so the normal ``output_type=TranscriptAnalysis`` path
    silently fails (the model returns ``{}`` for every tool call).

    Instead we build an agent that returns raw text, embed the expected JSON
    output format directly in the system prompt, and parse + validate the
    response ourselves.
    """
    from pydantic import TypeAdapter

    runtime_config = get_config()
    dc = duration_config or ClipDurationConfig.from_preset("medium")

    # Build an inlined, $ref-free version of the output schema
    full_schema = TranscriptAnalysis.model_json_schema()
    flat_schema = _inline_json_schema_refs(full_schema)
    schema_json = json.dumps(flat_schema, indent=2)

    system_prompt = _build_transcript_analysis_system_prompt(dc)
    system_prompt += (
        "\n\n## Output format (MANDATORY)\n"
        "You MUST respond with ONLY a single JSON object — no markdown, no "
        "code fences, no explanatory text. The JSON must conform to this "
        "schema:\n"
        f"```json\n{schema_json}\n```\n"
        "If the transcript is empty or has no usable segments, return:\n"
        '{"most_relevant_segments": [], "summary": "No usable segments found.", '
        '"key_topics": []}\n'
    )

    agent: Agent[None, str] = Agent(
        model=_build_transcript_model(runtime_config),
        system_prompt=system_prompt,
    )

    prompt = build_transcript_analysis_prompt(
        transcript=transcript,
        include_broll=include_broll,
        clip_signals=clip_signals,
        duration_config=dc,
    )
    # Reinforce JSON-only at the end of the user prompt as well.
    prompt += (
        "\n\nIMPORTANT: Reply with ONLY the JSON object. No other text."
    )

    result = await agent.run(prompt)
    raw = (result.output or "").strip()

    # Strip markdown code fences if the model wrapped the JSON
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()

    # Parse and validate against the original (non-inlined) model
    try:
        ta = TypeAdapter(TranscriptAnalysis)
        analysis: TranscriptAnalysis = ta.validate_json(raw)
        logger.info(
            "DeepSeek JSON analysis parsed successfully: %d segments",
            len(analysis.most_relevant_segments),
        )
        return analysis
    except Exception as parse_err:
        logger.error(
            "DeepSeek returned unparseable JSON. Raw (first 500 chars): %s",
            raw[:500],
        )
        raise RuntimeError(
            f"DeepSeek analysis returned invalid JSON: {parse_err}"
        ) from parse_err


async def get_most_relevant_parts_by_transcript(
    transcript: str,
    include_broll: bool = False,
    clip_signals: str | None = None,
    duration_config: Optional[ClipDurationConfig] = None,
) -> TranscriptAnalysis:
    """Get the most relevant parts of a transcript with virality scoring and optional B-roll detection.

    *duration_config* controls the target clip length and maximum number of
    clips the LLM should select. Pass ``ClipDurationConfig.from_preset("short")``
    for TikTok-style 15-30s clips, ``"medium"`` for 25-50s (default), or
    ``"long"`` for 45-90s podcast-style clips.
    """
    dc = duration_config or ClipDurationConfig.from_preset("medium")
    logger.info(
        f"Starting AI analysis of transcript ({len(transcript)} chars), "
        f"include_broll={include_broll}, duration={dc.ideal_min}-{dc.ideal_max}s"
    )

    try:
        runtime_config = get_config()
        provider, _ = _split_llm_name(runtime_config.llm)
        truncated = _truncate_transcript(transcript)

        if provider == "deepseek":
            # DeepSeek does not support nested $ref in function-calling parameter
            # schemas, so pydantic-ai output_type silently fails (model returns
            # empty {} tool arguments).  Fall back to a plain text agent with
            # explicit JSON-format instructions and parse the result ourselves.
            analysis = await _run_deepseek_analysis(
                transcript=truncated,
                include_broll=include_broll,
                clip_signals=clip_signals,
                duration_config=dc,
            )
        else:
            agent = get_transcript_agent(duration_config=dc)
            result = await agent.run(
                build_transcript_analysis_prompt(
                    transcript=truncated,
                    include_broll=include_broll,
                    clip_signals=clip_signals,
                    duration_config=dc,
                )
            )
            analysis = result.output
        logger.info(
            f"AI analysis found {len(analysis.most_relevant_segments)} segments"
        )

        # Validation with virality data handling
        validated_segments = []
        transcript_spans = _parse_transcript_spans(transcript)
        for segment in analysis.most_relevant_segments:
            # Validate text content
            if not segment.text.strip() or len(segment.text.split()) < 3:
                logger.warning(
                    f"Skipping segment with insufficient content: '{segment.text[:50]}...'"
                )
                continue

            # Validate timestamps - CRITICAL: start and end must be different
            if segment.start_time == segment.end_time:
                logger.warning(
                    f"Skipping segment with identical start/end times: {segment.start_time}"
                )
                continue

            # Parse timestamps to validate duration
            try:
                start_seconds = _parse_transcript_timestamp_seconds(
                    segment.start_time
                )
                end_seconds = _parse_transcript_timestamp_seconds(segment.end_time)

                duration = end_seconds - start_seconds

                if duration < dc.min_seconds or duration > dc.max_seconds:
                    repaired_bounds = _repair_segment_bounds(
                        segment,
                        transcript_spans,
                        start_seconds,
                        end_seconds,
                    )
                    if repaired_bounds:
                        start_seconds, end_seconds = repaired_bounds
                        duration = end_seconds - start_seconds

                if duration <= 0:
                    logger.warning(
                        f"Skipping segment with invalid duration: {segment.start_time} to {segment.end_time} = {duration}s"
                    )
                    continue

                if duration < dc.min_seconds:
                    logger.warning(
                        f"Skipping segment too short: {duration}s (min {dc.min_seconds}s required)"
                    )
                    continue

                if duration > dc.max_seconds:
                    logger.warning(
                        f"Skipping segment too long: {duration}s (max {dc.max_seconds}s allowed)"
                    )
                    continue

                # Validate virality scores
                if segment.virality:
                    # Ensure total score is sum of subscores
                    calculated_total = (
                        segment.virality.hook_score
                        + segment.virality.engagement_score
                        + segment.virality.value_score
                        + segment.virality.shareability_score
                    )
                    if segment.virality.total_score != calculated_total:
                        logger.warning(
                            f"Correcting virality total: {segment.virality.total_score} -> {calculated_total}"
                        )
                        segment.virality.total_score = calculated_total

                validated_segments.append(segment)
                virality_info = (
                    f", virality={segment.virality.total_score}"
                    if segment.virality
                    else ""
                )
                logger.info(
                    f"Validated segment: {segment.start_time}-{segment.end_time} ({duration}s){virality_info}"
                )

            except (ValueError, IndexError) as e:
                logger.warning(
                    f"Skipping segment with invalid timestamp format: {segment.start_time}-{segment.end_time}: {e}"
                )
                continue

        # Sort by virality score (primary) then relevance (secondary)
        validated_segments.sort(
            key=lambda x: (
                x.virality.total_score if x.virality else 0,
                x.relevance_score,
            ),
            reverse=True,
        )

        # Apply diversity filter to avoid near-duplicate clips from the same
        # part of the video or covering the same topic.
        diverse_segments = _filter_segment_diversity(validated_segments)

        final_analysis = TranscriptAnalysis(
            most_relevant_segments=diverse_segments,
            summary=analysis.summary,
            key_topics=analysis.key_topics,
            broll_opportunities=analysis.broll_opportunities if include_broll else None,
        )

        logger.info(f"Selected {len(diverse_segments)} segments for processing (diversity-filtered)")
        if diverse_segments:
            top = diverse_segments[0]
            logger.info(
                f"Top segment - relevance: {top.relevance_score:.2f}, virality: {top.virality.total_score if top.virality else 'N/A'}"
            )

        return final_analysis

    except Exception as e:
        logger.error(f"Error in transcript analysis: {e}")
        raise RuntimeError(f"Transcript analysis failed: {str(e)}") from e


def get_most_relevant_parts_sync(transcript: str) -> TranscriptAnalysis:
    """Synchronous wrapper for the async function."""
    return asyncio.run(get_most_relevant_parts_by_transcript(transcript))
