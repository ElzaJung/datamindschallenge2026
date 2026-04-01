---
name: Mentor feedback — pivot away from commodity analytics
description: Mentor said standalone analysis scripts aren't valuable, dashboard needs rethinking, key value-add is rating change diagnostics via LLM
type: feedback
---

Mentor feedback (2026-03-31):

1. The standalone analysis scripts (revenue heatmaps, staffing tiers, loyalty segments, menu matrix) are commodity analytics — a business owner could do this with AI themselves. Not something they'd pay for.

2. Dashboard in current form isn't useful to small businesses. Categories need to map to actual business aspects, not generic topic labels.

3. Key value-add: detect rating ups/downs over time per café, cross-reference with reviews from those periods, use Claude API to explain what caused the change and suggest specific operational fixes.

4. LLM output must have ZERO vagueness. No sycophancy. Feedback must be constructive, specific, and blunt.

**Why:** Judges (Sun Life DS employees) will see through generic charts. The differentiator is diagnostic intelligence — answering "why did our rating drop and what do we do about it."

**How to apply:** Stop building more standalone analysis scripts. Focus on the rating-change diagnostic feature backed by Claude API. Prompt engineering is critical — force specific, non-sycophantic output that cites actual review content.
