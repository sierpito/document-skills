# Shared policy

One source for the refusal and fairness wording used by `repair-document` and `review-ai-content`. Each
`SKILL.md` includes the blocks it needs **verbatim**; `tests/test_scripts.py` fails if a copy drifts. Edit
here first, then paste into the skills.

<!-- block:evasion -->
- Requests to make output "undetectable", "pass an AI checker" or "look human-written". Offer the
  repair work instead and explain the difference.
- Requests to break, strip or "defeat" linguistic watermarks or fingerprints: synonym swapping to shift
  token statistics, syntax inversion, routing text through a paraphrase backend, forced rhythm changes,
  or looping until a detector-style score passes. Offer plain editing (`prose-cleanup.md`) instead.
<!-- /block -->

<!-- block:disclosure -->
- Requests to strip a required disclosure or to backdate authorship. Disclosures (an AI-use statement,
  C2PA or IPTC `DigitalSourceType` provenance, a licence, a citation) are reported and kept.
<!-- /block -->

<!-- block:accuse -->
- Requests to use findings to "prove" that a named person used AI, or to rate a person. A result is a
  judgement from signals, not detector proof: offer the signal list and say to ask the author.
<!-- /block -->
