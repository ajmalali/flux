"""PromptPack composition (design.md §2)."""

from __future__ import annotations

from flux.executor import PromptPack


def make_pack() -> PromptPack:
    return PromptPack(
        system_prompt="You are the implement stage.",
        plan_summary="PLAN: ship the thing.",
        context_pack="FILES: src/a.py",
        stage_tail="FINDING 3 in review.json",
    )


def test_stable_prefix_excludes_stage_tail() -> None:
    """The prefix must be identical across stages of a ticket, so the cache hits."""
    pack = make_pack()
    other_stage = PromptPack(
        system_prompt="You are the review stage.",
        plan_summary=pack.plan_summary,
        context_pack=pack.context_pack,
        stage_tail="a completely different tail",
    )
    assert pack.stable_prefix == other_stage.stable_prefix
    assert pack.prompt != other_stage.prompt


def test_prompt_orders_prefix_then_tail_then_appendix() -> None:
    pack = make_pack().with_appendix("NUDGE: write review.json")
    prompt = pack.prompt
    assert prompt.index("PLAN:") < prompt.index("FILES:") < prompt.index("FINDING 3")
    assert prompt.index("FINDING 3") < prompt.index("NUDGE:")


def test_empty_sections_are_dropped() -> None:
    pack = PromptPack(system_prompt="sys", stage_tail="tail")
    assert pack.prompt == "tail"
    assert pack.stable_prefix == ""


def test_with_appendix_is_non_mutating_and_accumulates() -> None:
    pack = make_pack()
    once = pack.with_appendix("first")
    twice = once.with_appendix("second")
    assert pack.appendix == ""
    assert once.appendix == "first"
    assert twice.appendix == "first\n\nsecond"


def test_size_counts_system_prompt_and_prompt() -> None:
    pack = make_pack()
    assert pack.size_chars == len(pack.system_prompt) + len(pack.prompt)
    assert pack.approx_tokens == pack.size_chars // 4


def test_appendix_only_grows_the_pack_by_the_nudge() -> None:
    """The retry nudge must not rebuild the pack — only append to it."""
    pack = make_pack()
    nudged = pack.with_appendix("x" * 40)
    assert nudged.size_chars == pack.size_chars + len("\n\n") + 40
