---
id: PL-37
title: Writers infer authors' gendered pronouns from their names
status: Done
assignee: []
created_date: '2026-11-17T11:20:00Z'
updated_date: '2026-11-19T09:29:00Z'
labels:
  - agents
dependencies: []
type: docs
project: Accuracy
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Why:** in the 2026-11-17 cognitive-autonomy-ai review (PhilLit 0.5.47, 7 domains, 198 entries), four of the seven synthesis writers referred to cited authors as he, she, his or her: Danaher, Carter, Zagzebski, Gilbert, Hesselmann, Gerlich, Sharadin, Habgood-Coote, Sterelny and Königs. Nothing in the sources states these authors' pronouns. One writer avoided pronouns because no source gave them, so the writers do not follow one rule. A wrong guess misgenders a real person in a delivered review, and I replaced every instance by hand.

**Scope:** the synthesis-writer prompt should say to refer to authors by surname, or by "the paper" or "the authors", and never to infer a pronoun from a name. Optionally, `lint_md.py` could warn on he, she, his or her within a sentence that cites a work.
<!-- SECTION:DESCRIPTION:END -->
