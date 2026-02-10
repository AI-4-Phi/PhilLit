# PhilReview: A Purpose-Built AI Tool to help Philosophers Get Into a New Literature

Recent discussions on Daily Nous circled around the question whether philosophers should use AI in their research, and if so, how. We think that one research task that AI can be helpful with today is to provide an up-to-date overview of a literature in philosophy. But asking ChatGPT to do so won't do, because you can't trust to get the facts right, starting with which papers exist and are relevant, let alone how they relate to one another. Generic AI research agents fails at this, most obviously when fabricating citations, but also in failing to distinguish high-quality philosophical research from other content. 

We've built a tool that does better. It's called PhilReview, and it's open source. In this post, we want to explain what it does, and why we believe it addresses a real need. We want to test with you whether it lives up to the standards required for aiding serious philosophical research, and we are preparing a study to test the quality and usefulness of the reviews. if you want to be part of the study, read on!

## What PhilReview is for

PhilReview is for philosophers who want an up-to-date overview of a philosophical literature they don't know well. Maybe you're an ethicist who needs to understand debates in the epistemology of testimony. Maybe you work on philosophy of mind and want to engage with recent work on AI agency. Maybe you're writing a grant proposal that crosses subfield boundaries.

What do you do? You ask colleagues. But they may not work on the specific intersection you need. You look for an SEP article. It is excellent when one exists, but the Stanford Encyclopedia doesn't cover every topic, entries can lag years behind the latest work, and they're written for a general audience rather than oriented toward your specific question. You browse PhilPapers. It gives you papers but no map of the debate. In your despair, you ask ChatGPT. It is fast, but you can't trust the citations, and some of the sources it cites are obscure posts on Reddit. None of these gives you what you actually need: a reliable, up-to-date overview of a philosophical literature organized around the key debates and positions, with a verified bibliography you can start reading from.

## What PhilReview does

PhilReview tries to solve this problem. You give it a research topic or question, and it produces two things: an analytical overview of the literature (roughly 3,000–4,000 words) organized around key debates and positions, plus a verified bibliography in BibTeX format that you can import directly into your reference manager of choice.

Think of the output as something like a personalized, up-to-date SEP article, except tailored to your specific research question rather than written for a general audience.

To be clear about what PhilReview is *not*: it's not designed to write the literature review section of your paper, or to produce text for journal submissions or grant applications. It's a research tool. Its purpose is to give you a structured entry point to a literature you're unfamiliar with, so that you can then do the philosophical work yourself: read the key papers, form your own views, and identify where your contribution fits. The output is meant to be useful as a starting point, not as an endpoint.

## Is PhilReview better than ChatGPT?

You might wonder why we built a dedicated tool when you could just prompt the Research feature of Claude or ChatGPT with "write me a literature review on X." PhilReview is built on Anthropic's Claude, but it is designed from the ground up to meet the requirements of philosophical research. Three design features matter most:

**PhilReview searches relevant databases.** Every paper in the output was found by searching actual academic databases: PhilReview searches the Stanford Encyclopedia of Philosophy, PhilPapers, Semantic Scholar, OpenAlex, arXiv, and CrossRef. The system queries the same sources you'd search yourself, and nothing else

**PhilReview verifies every citation.** The system includes a verification process. Every bibliographic detail, e.g. title, author, journal name, volume number, page range, year in case of journal article, is checked against API data in bibliographic databases. If a detail can't be verified against an authoritative source, it's removed. This means the bibliography may occasionally have gaps (a missing volume number), but it won't contain fabrications.

**PhilReview is built for philosophy.** Most AI research tools are designed with biomedicine or computer science in mind. PhilReview searches the sources philosophers actually use, including PhilPapers, alongside general academic databases, and produces overviews organized around philosophical debates and positions.

## Is PhilReview any good in practice?

Are AI-generated literature overviews genuinely useful for philosophers? Are they accurate enough, comprehensive enough, analytically perceptive enough to serve as real entry points to unfamiliar literatures? This is not a question that can be settled in the armchair one way or another, and we don't know yet. We think the architecture we've built addresses some serious failure modes of other literature review agents, but we don't believe this should be settled by our say-so.

That's why we're designing a validation study. We're looking for philosophers willing to test PhilReview on topics they already know well, so they can evaluate whether the tool produces overviews that accurately represent the state of the literature, cite the right papers, and organize the field in a way that would genuinely help a newcomer get oriented. We think this kind of structured expert evaluation is the right way to assess whether a tool like this delivers on its promise.

## Try it or join the study

PhilReview is open source and available on GitHub: [PLACEHOLDER_URL]. The repository includes setup instructions, documentation, and example reviews.

If you're interested in participating in our validation study, we'd like to hear from you. We'll provide participants with an easy setup and pay for the the tokens needed to run reviews on topics of their expertise. We ask for structured feedback on accuracy, comprehensiveness, and usefulness. Contact us at [EMAIL].
