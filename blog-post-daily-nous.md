# Getting Into a New Literature: A Purpose-Built AI Tool for Philosophers

*By Johannes Himmelreich and Marco Meyer*

Recent discussions on Daily Nous — Justin Weinberg's [post on the ethics of AI in philosophical research](https://dailynous.com/2025/08/19/the-ethics-of-using-ai-in-philosophical-research/), Jimmy Licon's [account of his writing workflow](https://dailynous.com/2026/01/19/have-pen-laptop-and-chatgpt-will-publish-guest-post/), and the new [*Ethics* AI policy](https://dailynous.com/2025/12/03/ethics-announces-ai-policy/) — have been circling a question that we think needs to be sharpened. The question isn't just whether philosophers should use AI in their research. It's also what *kind* of AI tool is appropriate for which task. Asking ChatGPT to help brainstorm objections to your argument is a very different thing from asking it to produce a reliable overview of a philosophical literature. The first is a conversation; the second requires a tool you can trust to get the facts right — which papers exist, who wrote them, where they were published. Generic AI fails at this, because large language models routinely fabricate citations. But that doesn't mean AI can't help with this task. It means we need a tool built specifically to solve this problem.

We've built such a tool. It's called PhilReview, and it's open source. In this post, we want to explain what it does, why we think it addresses a real need, and why we believe the question of whether it actually works should be answered empirically.

## The problem: Entering a new literature

Every philosopher has experienced this: you're working on a project and realize it connects to a literature you don't know well. Maybe you're an ethicist who needs to understand debates in the epistemology of testimony. Maybe you work on philosophy of mind and want to engage with recent work on AI agency. Maybe you're writing a grant proposal that crosses subfield boundaries.

What do you do? You ask colleagues — but they may not work on the specific intersection you need. You look for an SEP article — excellent when one exists, but the Stanford Encyclopedia doesn't cover every topic, entries can lag years behind the latest work, and they're written for a general audience rather than oriented toward your specific question. You browse PhilPapers — which gives you papers but not structure: a list of results, not a map of the debate. Or you ask ChatGPT — which is fast, but you can't trust the citations. It will confidently cite papers that don't exist, by real authors, in real-sounding journals, with fabricated DOIs. And you have no reliable way to tell which citations are real and which are hallucinated.

None of these gives you what you actually need: a reliable, up-to-date overview of a philosophical literature organized around the key debates and positions, with a verified bibliography you can start reading from.

## What PhilReview does

PhilReview tries to solve this problem. You give it a research topic or question, and it produces two things: an analytical overview of the literature (roughly 3,000–4,000 words) organized around key debates, positions, and open questions, plus a verified bibliography in BibTeX format that you can import directly into Zotero or any reference manager.

Think of the output as something like a personalized, up-to-date SEP article — except tailored to your specific research question rather than written for a general audience.

To be clear about what PhilReview is *not*: it's not designed to write the literature review section of your paper, or to produce text for journal submissions or grant applications. It's a research tool. Its purpose is to give you a structured entry point to a literature you're unfamiliar with, so that you can then do the philosophical work yourself: read the key papers, form your own views, and identify where your contribution fits. The output is a starting point, not an endpoint.

## Why not just ask ChatGPT?

You might wonder why we built a dedicated tool when you could just prompt Claude or ChatGPT with "write me a literature review on X." The short answer: generic LLMs have a fundamental problem when it comes to this task. They fabricate citations. Not occasionally — routinely. They produce plausible-sounding papers with real-looking author names, realistic journal titles, and invented DOIs. For a literature overview to be useful to a philosopher, you need to trust that the papers it references actually exist and that the bibliographic details are correct.

PhilReview is built on Anthropic's Claude, but unlike a generic prompt, it is designed from the ground up around citation reliability. Three design features matter most:

**It searches real databases, not LLM memory.** Every paper in the output was found by searching actual academic databases: the Stanford Encyclopedia of Philosophy, PhilPapers, Semantic Scholar, OpenAlex, arXiv, and CrossRef. The system queries the same sources you'd search yourself, through their APIs. It doesn't rely on what the language model "remembers" from training data.

**It verifies every citation.** The system includes a multi-layered verification process. Every bibliographic detail — journal name, volume number, page range, year — is checked against the raw data returned by the database APIs. If a detail can't be verified against an authoritative source, it's removed rather than left in. This means the bibliography may occasionally have gaps (a missing volume number), but it won't contain fabrications.

**It's built for philosophy.** Most AI research tools are designed with biomedicine or computer science in mind. PhilReview searches the sources philosophers actually use — SEP and PhilPapers alongside general academic databases — and produces overviews organized around philosophical debates and positions rather than keyword clusters.

The result is a bibliography you can trust enough to start reading from, and an overview that gives you a structured map of the field's key questions.

## An empirical question

We want to be honest about what we don't yet know. Whether AI-generated literature overviews are genuinely useful for philosophers — accurate enough, comprehensive enough, analytically perceptive enough to serve as real entry points to unfamiliar literatures — is an empirical question. We think the architecture we've built addresses the most serious failure mode (fabricated citations), but we don't believe this should be settled by our say-so.

That's why we're designing a validation study. We're looking for philosophers willing to test PhilReview on topics they already know well, so they can evaluate whether the tool produces overviews that accurately represent the state of the literature, cite the right papers, and organize the field in a way that would genuinely help a newcomer get oriented. We think this kind of structured expert evaluation is the right way to assess whether a tool like this delivers on its promise — not marketing claims, not anecdotal impressions, but systematic feedback from domain experts.

## Try it or join the study

PhilReview is open source and available on GitHub: [PLACEHOLDER_URL]. The repository includes setup instructions, documentation, and example outputs.

If you're interested in participating in our validation study, we'd especially like to hear from you. We'll provide participants with the tokens needed to run reviews on topics of their expertise, and ask for structured feedback on accuracy, comprehensiveness, and usefulness. Contact us at [PLACEHOLDER_EMAIL].

Whether or not you try the tool, we think the broader point matters: the question of AI in philosophy shouldn't be answered in the abstract. It should be answered task by task, tool by tool, with evidence. We've built a tool for one specific task that philosophers face all the time. We'd like to find out — together with the community — whether it actually works.
