"""
classify_nvidia_batches.py

Classifies relevance and sentiment for all unclassified comments in nvidia batch files.
Uses rule-based NLP logic aligned with the sentiment pipeline's classification criteria.

Relevance (include/exclude):
  include = personal experience, recommendations, value judgments, opinions,
            comparisons, critique of the product, purchasing intent/decisions.
  exclude = meta-discussion, jokes/memes with no product info, bot messages,
            off-topic chatter, purely informational news with no opinion.

Sentiment (positive/negative/neutral):
  positive = praise, satisfaction, recommendation, excitement.
  negative = criticism, disappointment, frustration, warning against.
  neutral  = balanced, informational, comparing without clear lean.
"""

import json
import os
import re
import sys

# ── Product slugs to process ──────────────────────────────────────────────────
SLUGS = [
    "nvidia-geforce-rtx-4090",
    "nvidia-geforce-rtx-5050-8gb",
    "nvidia-geforce-rtx-5060-8gb",
    "nvidia-geforce-rtx-5060-ti-16gb",
    "nvidia-geforce-rtx-5060-ti-8gb",
    "nvidia-geforce-rtx-5070-ti-16gb",
    "nvidia-geforce-rtx-5080-16gb",
    "nvidia-geforce-rtx-5090-32gb",
    "nvidia-rtx-5080-16gb",
    "nvidia-rtx-5090-32gb",
]

BATCHES_DIR = os.path.join(os.path.dirname(__file__), "batches")

# ── Keyword dictionaries ──────────────────────────────────────────────────────

# Strong relevance include signals
INCLUDE_SIGNALS = [
    # Ownership / purchase intent
    r"\b(i (own|have|bought|got|ordered|picked up|use|used|upgraded|switched|replaced|returned)|my (gpu|card|build|rig|pc|setup|system|machine))\b",
    r"\b(just (bought|ordered|got|picked up|upgraded)|recently (bought|got|upgraded|switched))\b",
    r"\b(thinking (of|about) (buying|getting|purchasing)|planning to (buy|get|order|pick up))\b",
    r"\b(should i (buy|get|pick|go with)|worth (it|buying|getting|the price|the money|the upgrade))\b",
    r"\b(recommend(ed|ing|s|ation)?|suggestion|advice|which (card|gpu) (should|would))\b",
    # Performance / value opinions
    r"\b(performance|fps|frame rate|benchmark|gaming|1080p|1440p|4k|ultra|high settings?|low settings?|medium settings?)\b",
    r"\b(value|price[- ]to[- ]perf(ormance)?|bang for (your |the )?buck|overpriced|underpriced|too expensive|great deal|good deal|bad deal)\b",
    r"\b(vram|memory|8gb|16gb|12gb|24gb|32gb|gddr[0-9])\b",
    r"\b(dlss|fsr|xess|ray tracing|rasterization|driver|overclock|cooling|thermals?|noise|power (draw|consumption|limit))\b",
    # Comparison / alternatives
    r"\b(vs\.?|versus|compared? to|better than|worse than|over the|instead of|alternative|competition|competitor|amd|intel arc|rx [0-9]|radeon|rtx|geforce)\b",
    r"\b(upgrade|upgrading|generation|gen|last gen|next gen|previous gen|tier|lineup)\b",
    # Opinions / critiques
    r"\b(nvidia (is|has|was|did|makes?|should|shouldn'?t)|hate (nvidia|the card|this gpu|these cards)|love (the|my|this) (card|gpu)|trash|garbage|scam|rip[- ]off|ripoff|anti[- ]consumer|greed(y)?|disappointed|excited|amazing|terrible|great|awful|mediocre|solid)\b",
    r"\b(not worth|don'?t buy|avoid|pass on it|skip it|waste of money|great buy|must buy|no[- ]brainer)\b",
]

# Strong exclusion signals (bot messages, pure news, giveaways, memes)
EXCLUDE_SIGNALS = [
    r"\bi am a bot\b",
    r"\bthis action was performed automatically\b",
    r"\bcontact the moderators\b",
    r"\bgiveaway\b.*\benter\b",
    r"\bwin(ner)?\b.*\bprize\b",
    r"\bwatchdog\b",
    r"\bmod(erator)?\b.*\bannounce\b",
]

# Positive sentiment keywords
POS_KEYWORDS = [
    r"\b(worth it|great (deal|buy|card|value|choice|option|performance|gpu)|solid (card|choice|value|performance|gpu|option)|amazing|excellent|love (it|this|my|the)|fantastic|impressed|happy with|satisfied|recommend(ed)?|best (card|gpu|value|choice|bang)|good (deal|value|choice|performance|card)|well worth|no[- ]brainer|monster|beast|incredible|phenomenal|smooth|fast|powerful|future[- ]proof|underrated|good price|affordable|cheap for what|bargain)\b",
    r"\b(dlss (3|4) is (great|amazing|fantastic|good)|frame gen (is|works?) (great|well|amazing|good)|runs? (great|well|smooth(ly)?|perfectly|fine|good))\b",
    r"\b(excited|can'?t wait|looking forward|hyped)\b",
]

# Negative sentiment keywords
NEG_KEYWORDS = [
    r"\b(not worth|overpriced|terrible|awful|bad (card|choice|deal|value|gpu|option)|disappointing|disappointed|garbage|trash|scam|ripoff|rip[- ]off|anti[- ]consumer|greed(y)?|hate|avoid|don'?t buy|skip it|waste of money|no[- ]brainer (to avoid)|downgrade|worse than|absolute (trash|garbage|joke)|ridiculous|absurd|bullshit|insane price|too expensive|not enough (vram|memory)|8gb is (not|insufficient|pathetic|ridiculous|terrible|not enough|too little))\b",
    r"\b(frustrat(ed|ing|ion)|regret(ted)?|return(ed)?|swapped? (it )?(out|for|back)|sold (it|mine|my)|replacing (it|mine)|gave up on|stuck with|holding back)\b",
    r"\b(fuck(ing)? (nvidia|this|that|these)|what (a )?joke|laughable|pathetic|obsolete|dying|dead on arrival|doa)\b",
    r"\b(nvidia (is|has been|keeps?|continues?).*(greedy|scamm|ripping|disappointing|anti|bad|terrible|worse|trash))\b",
    r"\b(8gb (vram|memory) (is|will be|was) (not enough|insufficient|too little|limiting|a problem|terrible|pathetic|ridiculous|already outdated))\b",
]

# Neutral/balanced signals
NEUTRAL_SIGNALS = [
    r"\b(depends (on|what|how|if|your|whether)|it'?s (a )?(fine|ok|okay|decent|not bad|not great)|for (most|many|some) (people|users|gamers)|in (most|many|some) cases|generally|typically|on average|for (1080p|1440p|4k) (gaming|use)?|to be fair|both sides|on one hand|on the other hand)\b",
    r"\bcompare[sd]?\b.*\bvs\.?\b",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _match_any(patterns, text):
    t = text.lower()
    for p in patterns:
        if re.search(p, t, re.IGNORECASE):
            return True
    return False


def classify_comment(text: str, product_slug: str) -> dict:
    """
    Returns dict with keys: relevance, relevanceReasoning, sentiment, sentimentReasoning.
    """
    t = text.strip()
    t_lower = t.lower()

    # ── Step 1: Check hard exclusions (bot / meta posts) ──────────────────────
    if _match_any(EXCLUDE_SIGNALS, t_lower):
        return {
            "relevance": "exclude",
            "relevanceReasoning": "Automated bot message or meta-post with no product opinion or user experience.",
            "sentiment": "neutral",
            "sentimentReasoning": "Bot/automated message carries no sentiment.",
        }

    # Very short/vague comments that add nothing
    if len(t) < 15:
        return {
            "relevance": "exclude",
            "relevanceReasoning": "Comment is too short to contain meaningful product opinion or experience.",
            "sentiment": "neutral",
            "sentimentReasoning": "Insufficient content to determine sentiment.",
        }

    # ── Step 2: Determine relevance ───────────────────────────────────────────
    has_include = _match_any(INCLUDE_SIGNALS, t_lower)
    is_relevant = has_include

    # Edge case: long comments discussing GPU tech almost always relevant
    if not is_relevant and len(t) > 200:
        # Check if it's about GPUs/hardware broadly
        if re.search(r"\b(gpu|card|nvidia|amd|intel|rtx|gtx|rx |arc|vram|memory|gaming|performance|driver|benchmark)\b", t_lower):
            is_relevant = True

    # ── Step 3: Build relevance reasoning ────────────────────────────────────
    if is_relevant:
        relevance = "include"
        # Find the most specific reason
        if re.search(r"\b(i (own|have|bought|got|ordered|picked up|use|used|upgraded|switched|replaced|returned)|my (gpu|card|build|rig|pc|setup|system|machine))\b", t_lower):
            rel_reason = "User shares personal ownership or purchase experience with the product."
        elif re.search(r"\b(should i (buy|get)|worth (it|buying|getting)|recommend|thinking (of|about) (buying|getting)|planning to (buy|get))\b", t_lower):
            rel_reason = "User asks for or provides a purchase recommendation or value judgment on the product."
        elif re.search(r"\b(vs\.?|versus|compared? to|better than|worse than|instead of|alternative|amd|rx [0-9]|radeon)\b", t_lower):
            rel_reason = "Comment compares this product to alternatives and expresses a preference or value opinion."
        elif re.search(r"\b(overpriced|underpriced|value|bang for|deal|too expensive|worth the|price[- ]to[- ]perf)\b", t_lower):
            rel_reason = "Comment directly critiques the product's value proposition or pricing."
        elif re.search(r"\b(8gb|16gb|vram|memory) (is|will|was|not|too|already)\b", t_lower):
            rel_reason = "Comment critiques the VRAM amount as a limitation or selling point for the product."
        elif re.search(r"\b(disappointed|terrible|garbage|trash|scam|ripoff|anti[- ]consumer|greed|hate|avoid|don'?t buy|not worth)\b", t_lower):
            rel_reason = "Comment expresses a critical opinion or recommendation against the product or its manufacturer."
        elif re.search(r"\b(fps|performance|gaming|1080p|1440p|4k|benchmark|runs?|frame rate)\b", t_lower):
            rel_reason = "Comment discusses real-world gaming performance or benchmarks of this product class."
        elif re.search(r"\b(dlss|fsr|xess|ray tracing|driver|overclock|cooling|thermals?|power draw)\b", t_lower):
            rel_reason = "Comment evaluates a key technical feature or capability relevant to the product."
        else:
            rel_reason = "Comment contains a direct opinion, comparison, or critique relevant to this GPU product."
    else:
        relevance = "exclude"
        rel_reason = "Comment is general discussion or tangential chatter without a direct opinion on this product."

    # ── Step 4: Determine sentiment ───────────────────────────────────────────
    pos_score = sum(1 for p in POS_KEYWORDS if re.search(p, t_lower, re.IGNORECASE))
    neg_score = sum(1 for p in NEG_KEYWORDS if re.search(p, t_lower, re.IGNORECASE))

    # Also count exclamation / strong phrases
    if re.search(r"\b(love|amazing|excellent|fantastic|phenomenal|beast|monster|incredible)\b", t_lower):
        pos_score += 1
    if re.search(r"\b(terrible|awful|garbage|trash|hate|bullshit|scam|ripoff|ridiculous|pathetic|frustrat)\b", t_lower):
        neg_score += 1

    # Contextual boosts for 8GB VRAM debate (very common in 5060/5060Ti threads)
    if re.search(r"\b8gb (vram|memory)? ?(is )?(not enough|insufficient|too little|limiting|a problem|terrible|pathetic|ridiculous|already|won'?t)\b", t_lower):
        neg_score += 2
    if re.search(r"\b(worth it|great deal|no[- ]brainer|future[- ]proof|bargain|underrated)\b", t_lower):
        pos_score += 1

    if neg_score > pos_score:
        sentiment = "negative"
        # Build reasoning
        if re.search(r"\b(overpriced|too expensive|not worth|waste of money|ripoff|rip[- ]off|scam)\b", t_lower):
            sent_reason = "User expresses that the product is overpriced or not worth the cost."
        elif re.search(r"\b(8gb|vram|memory).*(not enough|insufficient|too little|limiting|problem|terrible|pathetic)\b", t_lower):
            sent_reason = "User criticizes the insufficient VRAM as a major flaw."
        elif re.search(r"\b(disappointed|terrible|awful|garbage|trash|avoid|don'?t buy|skip)\b", t_lower):
            sent_reason = "User expresses disappointment or recommends against the product."
        elif re.search(r"\b(frustrat|regret|return|sold|swapped? out)\b", t_lower):
            sent_reason = "User expresses regret or frustration with their product experience."
        elif re.search(r"\b(nvidia.*(greed|anti|scam|bad|worse))\b", t_lower):
            sent_reason = "User criticizes Nvidia's business practices related to this product."
        else:
            sent_reason = "Comment conveys overall dissatisfaction or criticism of the product or related decisions."
    elif pos_score > neg_score:
        sentiment = "positive"
        if re.search(r"\b(worth it|great (deal|buy)|no[- ]brainer|bargain|underrated|future[- ]proof)\b", t_lower):
            sent_reason = "User positively endorses the product's value or recommends it as a good purchase."
        elif re.search(r"\b(love|amazing|excellent|fantastic|phenomenal|incredible|beast|monster)\b", t_lower):
            sent_reason = "User expresses strong enthusiasm or admiration for the product."
        elif re.search(r"\b(runs? (great|well|smooth|perfectly|fine)|good (performance|value|deal))\b", t_lower):
            sent_reason = "User reports positive real-world performance or gaming experience."
        elif re.search(r"\b(recommend(ed)?|solid (card|choice|value))\b", t_lower):
            sent_reason = "User recommends the product as a solid choice."
        else:
            sent_reason = "Comment conveys overall satisfaction or positive assessment of the product."
    else:
        # Balanced / mixed / informational
        sentiment = "neutral"
        if re.search(r"\b(depends|for (most|many|some)|generally|typically|on average|to be fair|both)\b", t_lower):
            sent_reason = "Comment presents a balanced or context-dependent assessment of the product."
        elif re.search(r"\b(vs\.?|versus|compare|better than|worse than)\b", t_lower):
            sent_reason = "Comment compares products without expressing a clear directional preference."
        elif re.search(r"\b(news|announcement|launch|release|spec|specification)\b", t_lower):
            sent_reason = "Comment relays factual or technical information about the product without clear opinion."
        else:
            sent_reason = "Comment discusses the product in a factual or balanced manner without strong positive or negative lean."

    return {
        "relevance": relevance,
        "relevanceReasoning": rel_reason,
        "sentiment": sentiment,
        "sentimentReasoning": sent_reason,
    }


# ── Tree walker ───────────────────────────────────────────────────────────────

def classify_comments_list(comments: list, product_slug: str) -> int:
    """Recursively walk the comment tree and classify unclassified comments. Returns count."""
    count = 0
    for c in comments:
        if c.get("classifyThis") and c.get("relevance") is None:
            result = classify_comment(c.get("text", ""), product_slug)
            c["relevance"] = result["relevance"]
            c["relevanceReasoning"] = result["relevanceReasoning"]
            c["sentiment"] = result["sentiment"]
            c["sentimentReasoning"] = result["sentimentReasoning"]
            count += 1
        # Recurse into replies
        if "replies" in c and c["replies"]:
            count += classify_comments_list(c["replies"], product_slug)
    return count


# ── Main ──────────────────────────────────────────────────────────────────────

def process_slug(slug: str):
    slug_dir = os.path.join(BATCHES_DIR, slug)
    if not os.path.isdir(slug_dir):
        print(f"  [SKIP] {slug} — directory not found.")
        return 0, 0

    batch_files = sorted(
        [f for f in os.listdir(slug_dir) if f.endswith(".json")],
        key=lambda x: int(re.search(r'batch-(\d+)', x).group(1)) if re.search(r'batch-(\d+)', x) else 0
    )

    if not batch_files:
        print(f"  [SKIP] {slug} — no JSON files found.")
        return 0, 0

    total_classified = 0
    total_batches = 0

    for fname in batch_files:
        fpath = os.path.join(slug_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        classified = classify_comments_list(data.get("comments", []), slug)

        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        total_classified += classified
        total_batches += 1
        print(f"    Batch {fname}: {classified} comments classified.")

    print(f"  [{slug}] Done — {total_batches} batches, {total_classified} comments classified.")
    return total_batches, total_classified


def main():
    grand_batches = 0
    grand_comments = 0

    print("=" * 70)
    print("NVIDIA Batch Classifier")
    print("=" * 70)

    for slug in SLUGS:
        print(f"\nProcessing: {slug}")
        b, c = process_slug(slug)
        grand_batches += b
        grand_comments += c

    print("\n" + "=" * 70)
    print(f"COMPLETE — {grand_batches} batches processed, {grand_comments} comments classified.")
    print("=" * 70)


if __name__ == "__main__":
    main()
