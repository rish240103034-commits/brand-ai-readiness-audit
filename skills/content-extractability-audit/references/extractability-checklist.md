# Extractability checklist (gate 3, continued: is the fact in readable text?)

A fact only gets quoted if a machine can read it as text. These signals find facts that are
present to the eye but absent to the parser.

| Signal | How detected | Why it matters | Severity |
|---|---|---|---|
| Missing `<title>` | empty/absent title tag | The single strongest label a machine reads; its absence blinds every downstream summary. | high |
| Missing meta description | no `<meta name=description>` | Frequently quoted verbatim as the page summary in results and answers. | medium |
| Duplicate titles | same title string across pages | Machines can't tell pages apart or pick the right one to cite. | low |
| Missing H1 | no `<h1>` | No primary topic anchor for the page. | medium |
| Multiple H1s | > 1 `<h1>` | Dilutes the topic signal. | low |
| Images missing alt | > 30% of sampled images and ≥ 3 with no `alt` | Any fact carried by the image (logo text, infographic, spec) is invisible to text machines. | medium |
| Likely text-in-images | ≥ 5 images, < 120 visible words, > 3 KB HTML | Offers/specs/contact baked into pictures aren't extractable. | medium |
| Undeclared language | no `<html lang>` on any page | Misrouted interpretation and audience targeting. | low |
| PDF-locked content | ≥ 3 PDF links across the sample | Scanned/image PDFs are often unreadable to crawlers. | low |

## The underlying rule
State the fact in plain HTML text, near a descriptive heading, once and unambiguously.
Supplementary media is fine — but the *fact itself* (price, address, hours, claim, spec) must
also exist as selectable text, and any informative image should carry `alt` that mirrors its
words.

## Why text-in-image is medium confidence
Without OCR (excluded to stay portable and fast), the skill infers embedded text from a page
being visually rich yet textually thin. That correctly catches "hero banner with the offer in
a JPG" while staying honest that it is an inference, not a read of the pixels.
