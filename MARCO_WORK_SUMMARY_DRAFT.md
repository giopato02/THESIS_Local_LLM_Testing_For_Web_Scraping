<!--
RULES FOR THIS REPORT (received 2026-09-22)
  * at most 10 pages in total, roughly one page per section below
  * general and readable: no code, no script names, no file paths
  * a summary, not a rigid grid of timeframes and tasks. Name the strategies
    used and their results: "In June I spent three weeks on X. It did not work
    because Y, so I tried Z. The result was W."
Source material: THESIS_NOTES.md (failed approaches in section 4c, the pipeline
in 3.13f to 3.13n, the ground-truth method in 3.14).
Sections marked "to write" are still open.
-->

# NeoHub, work package 1: extracting company data from innovation network websites

Work summary for Neovation. Author: Giorgi Pataridze (Constructor University
Bremen).

## 1. The task

*To write.* What NeoHub needs from this work package: for each innovation
network, the list of member companies with their websites and contact details.
The two questions: which local AI model and prompting approach does this best,
and what a complete pipeline can deliver.

## 2. Collecting and downloading the network pages

*To write.* Building the list of member pages, and what made downloading
harder than expected: pages that only load in a browser, cookie banners,
blocked requests.

## 3. Comparing local models and prompting strategies

*To write.* Three local models and three prompting strategies, tested on the
hand-written company lists. The winner, and the finding that the largest model
was neither the most accurate nor the fastest.

## 4. From company names to full records

*To write.* Asking for websites and addresses as well as names, what that cost
in accuracy and time, and why a model that wins on names can lose on websites.

## 5. Finding the missing websites

*To write.* Why no single step supplies most websites: reading them off the
network page, opening each member's profile page, and a web search whose
results are checked before use. The final company list and its coverage.

## 6. Choosing the test pages (September 2026)

To know how accurate the extraction is, we compare what the models find with
member lists written out by hand, page by page. These are called the ground
truth. The first round covered 10 network pages with about 760 companies. In
September the ground truth was extended by 20 pages. The aim was that the 30
pages together show the variety of the 291 networks, rather than many copies
of the same kind of page.

We started from all 291 member pages. Only 153 contain a member list that can
be read directly; the others load their list only inside a browser, are almost
empty, or could not be reached. Six of the 153 were already in the first
round, and on 14 the company names appear only in running text rather than as
a list. That left 133 candidates.

For each candidate we measured, without using any AI model, how the list is
laid out (six kinds, from plain lists of names to tables and walls of logos),
how long it is, whether the network is a ZIM network or privately funded,
which consultancy manages it, and whether its website is a near-copy of other
network websites. Several consultancies run many networks on the same website
template; the largest such family has 11 sites.

We then chose 20 pages that cover every layout, range from about a dozen to
about 330 companies, include eight long pages and seven ZIM networks, and use
each website family and each consultancy only once. Every candidate was opened
and read. Four were rejected at that point: two listed associations rather
than companies, one loaded only its first ten members, and one linked to a
different organisation's list.

A final check looked for member lists spread over several pages. Two of the
chosen pages showed only their first page, one of more than 500 members and
one of more than 4,000, and were replaced. The same check showed that four of
the original ten pages are only the first page of a longer list. Their
accuracy figures remain valid, because the models and the hand-written lists
used the same page. But for those networks the final company list is less
complete than the figures suggest. Following multi-page lists is therefore
planned as part of the download step for the full run over all networks.

Writing out the 20 new pages by hand means roughly 1,450 companies, about
twice the first round.

One observation from this work is worth passing on. Five weeks after the pages
were saved, one of the twenty networks had taken its website offline
completely, and a second network in the same group had done the same. Both are
publicly funded networks that run for a fixed period and close when the funding
ends. Company data collected from such sources goes out of date quickly, so any
database built on them needs to be refreshed on a schedule, and the entries
coming from time-limited networks are the ones to re-check first.

## 7. What did not work, and why

*To write.* The approaches that were tried and dropped, as Marco asked to see.

## 8. Results and open points

*To write.* The final numbers, the comparison with cloud models (running in
parallel), and what remains for the full run over all networks.
