---
name: content-extractability-audit
description: >-
  Detect facts that are visible to a human but invisible to a machine because they
  are locked in non-text or lack textual anchors. Checks page title and meta
  description, heading structure (H1/outline), image alt text and likely
  text-in-images, declared page language, and content offloaded to PDFs. Use when
  a brand's key facts (offers, specs, contact details) don't show up in AI answers
  even though they're plainly on the page. Read-only.
license: MIT
allowed-tools: [Bash]
metadata:
  dimension: discoverability
  checks: [extractability]
---

# Content Extractability Audit

Mechanism (Round-2 appendix C): the more explicitly and unambiguously a fact is stated in
plain, readable text, the more reliably a machine extracts and repeats it; the more it is
implied, buried, or locked in an image/PDF, the more likely it is missed.

## When to use
Facts a person can clearly see (prices, hours, contact info, value proposition) don't appear
in AI answers; pages are image-heavy or PDF-driven; titles/headings are missing or generic.

## Inputs
`url` (required); optional `--max-pages N`.

## Procedure
1. **Textual anchors**: missing/duplicate `<title>`, missing meta description.
2. **Outline**: missing H1, multiple H1s.
3. **Images**: high proportion of images with no `alt`; image-heavy + text-thin pages where
   copy is likely baked into pictures.
4. **Language**: undeclared `<html lang>`.
5. **PDF-locked content**: substantive information offloaded to PDF files (often unreadable
   scans).

See [extractability-checklist](references/extractability-checklist.md).

## Output
Findings in the `extractability` category with evidence and specific "move this fact into
readable text / add alt / add title" actions. Standalone:
```bash
python skills/content-extractability-audit/scripts/run.py https://example.com
```

## Guardrails
Read-only; no OCR or asset downloads — text-in-image is inferred from the text/image balance
and reported at medium confidence.
