# OCR Eval Plan (Deferred Re-OCR)

## Context
- The current `pdftotext` output has OCR artifacts inherited from the PDF's text layer.
- Re-running OCR is deferred for now; the immediate goal is to design an evaluation that quantifies current quality and guides future cleanup decisions.

## Eval Goal
- Primary: measure text quality improvements from cleanup without re-OCR.
- Secondary: provide evidence for whether a future OCR redo is worth the cost.

## Scope
- Compare two candidates:
  1) Current `pdftotext` output.
  2) A cleaned/normalized version of that output.
- No OCR engine changes in this phase.

## Sampling Strategy
- Sample 20-50 pages across the PDF:
  - Early, middle, late sections.
  - Include hard pages (faded, skewed, dense text, footnotes).
- Keep the same page set for all candidate outputs.

## Gold Text Creation
- Manually correct the sampled pages into a gold reference.
- Standardize cleanup rules, e.g.:
  - Fix broken hyphenation across line breaks.
  - Normalize ligatures (fi, fl).
  - Remove stray glyphs or repeated characters.
  - Preserve original punctuation and casing unless clearly erroneous.
- Maintain a short checklist to keep edits consistent across pages.

## Metrics
- CER (Character Error Rate).
- WER (Word Error Rate).
- Artifact counters (simple regex-based counts):
  - Hyphenation breaks: patterns like "word-\nnext".
  - Junk glyphs: non-ASCII symbols outside known ligatures.
  - Repeated character runs (e.g., "lll" or "....").

## Scoring Approach
- Use comparative scoring: candidate A vs candidate B against the gold.
- Optional absolute targets (adjust as needed):
  - CER < 2.0%
  - WER < 5.0%
- Prefer the candidate with lower CER/WER and fewer artifacts.

## Deliverables
- A page list used for evaluation.
- Gold reference text for those pages.
- A short report with:
  - CER/WER for each candidate.
  - Artifact counts.
  - A recommendation (keep current, improve cleanup, or revisit OCR).

## Future OCR Redo Trigger
- If CER/WER remain high after cleanup, or artifact counts remain elevated,
  consider re-running OCR with higher-quality settings.
