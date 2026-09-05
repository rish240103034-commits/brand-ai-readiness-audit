# Corroboration & disambiguation checklist (agreement half of appendix D)

Mechanism: a claim in only one place is fragile; the same fact across many independent
sources is believed and repeated. And when several things share a name, a system mixes them
up unless something distinguishes the brand.

## Corroboration signals
| Signal | How detected | Why it matters | Severity |
|---|---|---|---|
| Organization without `sameAs` | Org/LocalBusiness node present, no `sameAs` | `sameAs` links the site to Wikipedia/Wikidata/LinkedIn/Crunchbase — the independent sources that corroborate identity. | medium |
| No external profile presence | no links to recognized social/authority/reviews/maps hosts | The brand is an island; assistants find no second source to confirm claims. | medium (reported low→medium) |

## Disambiguation signals
| Signal | How detected | Why it matters | Severity |
|---|---|---|---|
| Ambiguous name, no distinguishers | short/generic brand name **and** no address/foundingDate/founder/legalName/sameAs anywhere | Namesakes get conflated; the wrong entity gets cited. | medium |
| Conflicting `og:site_name` | different ASCII names across same-language pages that share no token | Weakens entity resolution. Localized (different-language) names are ignored to avoid false positives. | low |

## The fix
- Add `sameAs` to the Organization node pointing at the brand's Wikidata/Wikipedia, LinkedIn,
  Crunchbase, and primary socials.
- Claim and interlink profiles on independent platforms and directories; consistency across
  them is what makes a fact credible to an assistant.
- Disambiguate with concrete facts (legalName, foundingDate, founder, address) in both schema
  and prose, so the brand is unmistakably itself.

## Why this stays read-only and portable
The skill inspects only links and markup the site already ships. It does **not** crawl
third-party sites or call external APIs (which would break the self-contained, < 5 min,
robots-respecting guardrails). It tells the brand *where corroboration is missing*; verifying
each external profile is a follow-up a human or a networked tool can do.
