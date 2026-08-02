#!/usr/bin/env python3
"""Generate the HARD corpus: longer, messier documents that stress quoting.

  hard_annual_report.txt  — ~2,300 words, OCR-style damage: words hyphen-split
                            across line breaks, page footers interleaved with
                            body text, erratic double spaces
  hard_transcript.txt     — ~2,600 words, meeting transcript: timestamps,
                            filler, interruptions; facts buried mid-ramble
  hard_email_thread.txt   — ~2,000 words, quoted-reply chain: key sentences
                            recur at multiple '>' quote depths (repetition
                            traps), repeated legal footers

Deterministic (seeded). Writes docs to corpus/docs/ and questions to
corpus/questions_hard.json. Run validate_corpus.py afterwards.
"""
import json
import random
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "corpus" / "docs"
rng = random.Random(20260730)

# ---------------------------------------------------------------- H1: report
REPORT_FACTS = [
    ("Consolidated revenue for fiscal 2025 was $2,847.3 million, an increase of 8.6% over the prior year.", "2,847.3"),
    ("Research and development expense totaled $412.6 million, representing 14.5% of consolidated revenue.", "412.6"),
    ("At year end the Company employed 11,204 people across 23 countries.", "11,204"),
    ("The Board declared a quarterly dividend of $1.15 per share, payable January 15, 2026.", "$1.15"),
    ("The Company recorded a goodwill impairment charge of $88.2 million related to the Coatings reporting unit.", "88.2"),
    ("The effective tax rate for fiscal 2025 was 21.4%, compared with 23.9% in fiscal 2024.", "21.4%"),
    ("Order backlog at year end stood at $5.1 billion, of which approximately 62% is expected to convert to revenue within twelve months.", "$5.1"),
    ("The Advanced Polymers segment reported operating income of $301.8 million on revenue of $1,204.9 million.", "301.8"),
]

REPORT_FILLER = [
    "To our shareholders: fiscal 2025 tested the resilience of our operating model and, in our judgment, affirmed it. Demand conditions diverged sharply by end market, with aerospace and electronics applications remaining robust while construction-adjacent volumes softened for the second consecutive year.",
    "Our strategy remains unchanged: concentrate capital in specialty applications where technical service creates switching costs, divest commodity lines where price is the only lever, and maintain an investment-grade balance sheet through the cycle.",
    "Safety performance improved for the fourth consecutive year. The total recordable incident rate declined to levels that place the Company in the first quartile of our peer group, an outcome we attribute to the behavioral safety program rolled out across all manufacturing sites.",
    "The integration of the Herzfeld acquisition proceeded ahead of schedule. Procurement synergies were realized earlier than modeled, and the combined commercial organization has been selling the full product portfolio since the second quarter.",
    "Raw material costs were volatile throughout the year. Propylene and specialty monomer prices rose sharply in the first half before retreating, and our margin performance reflects both the lag in contractual pass-through mechanisms and disciplined pricing execution by our commercial teams.",
    "We continued to rationalize our manufacturing footprint. The previously announced closure of the Gary, Indiana compounding facility was completed in the third quarter, with production successfully transferred to Monterrey and Krakow.",
    "Working capital discipline remained a priority. Days sales outstanding improved modestly, and inventory turns recovered to pre-disruption levels as supply chain normalization allowed a reduction in safety stock positions.",
    "The Company's sustainability commitments advanced on schedule. Scope 1 and 2 emissions intensity declined year over year, and the renewable electricity share of our total consumption reached the interim target established in our 2022 climate framework.",
    "Our capital allocation priorities are unchanged: organic investment first, followed by the dividend, bolt-on acquisitions that meet our return thresholds, and opportunistic share repurchases with residual free cash flow.",
    "Litigation and environmental remediation matters are described in the notes to the consolidated financial statements. Management does not currently expect resolved or pending matters to have a material effect on the Company's financial position.",
    "Segment reporting was realigned at the beginning of the fiscal year to reflect the new management structure. Prior-period amounts have been recast for comparability, and a reconciliation is provided in Note 3.",
    "The Industrial Coatings segment experienced continued pricing pressure in architectural applications, partially offset by share gains in powder coatings for the energy transition, where demand for corrosion-resistant systems used in transmission infrastructure grew at a double-digit rate.",
    "Currency translation reduced reported revenue growth by approximately two percentage points, driven principally by the weakening of the euro and the Japanese yen against the U.S. dollar during the first half of the fiscal year.",
    "Information technology investments focused on the multi-year enterprise resource planning consolidation, which reached its third of five planned deployment waves without material disruption to customer service levels.",
]


def build_report() -> str:
    paras = REPORT_FILLER[:]
    # plant each fact inside a filler paragraph so it is buried mid-text
    slots = rng.sample(range(len(paras)), len(REPORT_FACTS))
    for (fact, _), slot in zip(REPORT_FACTS, slots):
        p = paras[slot]
        cut = p.find(". ", len(p) // 3)
        cut = cut + 2 if cut != -1 else len(p)
        paras[slot] = p[:cut] + fact + " " + p[cut:]
    body = "TITAN MATERIALS GROUP\nANNUAL REPORT — FISCAL 2025\n\n" + "\n\n".join(paras)

    # OCR damage pass -------------------------------------------------------
    protected = re.compile(r"[\d$%,.]")

    def hyphenate_wrap(text: str) -> str:
        out_lines = []
        for para in text.split("\n\n"):
            wrapped = textwrap.wrap(para, width=78)
            i = 0
            while i < len(wrapped) - 1:
                line, nxt = wrapped[i], wrapped[i + 1]
                first_next = nxt.split(" ", 1)[0]
                # randomly split a long clean word across the line break
                if (len(first_next) >= 8 and first_next.isalpha()
                        and not protected.search(first_next) and rng.random() < 0.35):
                    k = rng.randrange(3, len(first_next) - 2)
                    wrapped[i] = line + " " + first_next[:k] + "-"
                    wrapped[i + 1] = first_next[k:] + nxt[len(first_next):]
                i += 1
            out_lines.extend(wrapped)
            out_lines.append("")
        return "\n".join(out_lines)

    damaged = hyphenate_wrap(body)
    # interleave page footers
    lines = damaged.split("\n")
    out, page = [], 3
    for n, ln in enumerate(lines):
        out.append(ln)
        if n and n % 34 == 0:
            out.append("")
            out.append(f"TITAN MATERIALS GROUP · 2025 ANNUAL REPORT                        Page {page}")
            out.append("")
            page += 1
    # erratic double spaces
    text = "\n".join(out)
    words = text.split(" ")
    injected = 0
    while injected < 30:
        j = rng.randrange(1, len(words))
        # never widen the gap inside or next to a numeric value
        if any(c.isdigit() or c == "$" for c in words[j - 1] + words[j]):
            continue
        words[j] = " " + words[j]
        injected += 1
    return " ".join(words)


# ------------------------------------------------------------ H2: transcript
TR_SPEAKERS = ["PRIYA", "MARCUS", "DANA", "TOM"]
TR_FACTS = [
    ("PRIYA", "Okay so, hard numbers: the revised marketing budget is $340K for the quarter, down from $410K, and that is not a discussion item, that came from finance.", "$340K"),
    ("MARCUS", "We are locked on March 9th for the public launch, um, and I mean locked — press embargo lifts that morning.", "March 9th"),
    ("DANA", "Monthly churn ticked up to 4.7% in June, which, look, some of that is the pricing change but not all of it.", "4.7%"),
    ("MARCUS", "I need six backend engineers by end of quarter or the migration slips, full stop, I've said this in three meetings now.", "six"),
    ("TOM", "So the Datadog quote came in at $78,000 a year for the new tier, which is, yeah, a lot, but the old plan caps out.", "$78,000"),
    ("DANA", "For what it's worth NPS is sitting at 41, up three points since the onboarding redesign shipped.", "41"),
    ("DANA", "Trial-to-paid conversion was 2.3% last month, still below where we modeled it, um, but trending the right way.", "2.3%"),
    ("PRIYA", "The security review has to be done by August 15, no exceptions, legal was extremely clear about that.", "August 15"),
]

TR_FILLER = [
    "Yeah, um, can everyone see my screen? Okay, cool, cool.",
    "Sorry, I was on mute. Classic. What I was saying was, we should probably take that offline.",
    "I mean, I don't disagree, I just think we're solving next quarter's problem this quarter.",
    "Wait, before we move on — did anyone follow up with the platform team about that? No? Okay, action item.",
    "Can we park the offsite discussion? It's eating our agenda every single week.",
    "[crosstalk]",
    "Honestly the dashboard numbers and the warehouse numbers still don't agree, so take everything I'm about to say with a grain of salt.",
    "That's fair, that's fair. Okay.",
    "Um, so, quick tangent, the parking garage badge readers are still broken, facilities says next week, I'll believe it when I see it.",
    "Let's timebox this to five minutes because we have to get to roadmap.",
    "I'll drop the doc in the channel after this, everyone please actually read it this time.",
    "Hmm, yeah, I don't have that number in front of me, let me get back to you.",
    "Right, and to be clear this is the same thing we said last quarter, so nobody should be surprised.",
    "Sorry, my dog is going insane, one second. Okay. Where were we.",
    "Do we have a decision or are we just admiring the problem? Genuine question.",
    "New phone, who dis — sorry, wrong window, ignore that, someone was messaging me.",
]


def build_transcript() -> str:
    lines = ["PRODUCT PLANNING SYNC — RAW TRANSCRIPT (AUTO-GENERATED, UNEDITED)",
             "Recorded meeting, 4 participants, 47 minutes", ""]
    t = 63  # seconds
    events = []
    for filler in TR_FILLER * 3:
        events.append((rng.choice(TR_SPEAKERS), filler))
    fact_positions = sorted(rng.sample(range(4, len(events) - 2), len(TR_FACTS)))
    for pos, (spk, fact, _) in zip(fact_positions, TR_FACTS):
        events.insert(pos, (spk, fact))
    for spk, utterance in events:
        t += rng.randrange(20, 95)
        stamp = f"[00:{t // 60:02d}:{t % 60:02d}]"
        lines.append(f"{stamp} {spk}: {utterance}")
        lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------- H3: email chain
EM_FACTS = [
    ("The total contract value for the 24-month term is $1.2 million.", "$1.2 million"),
    ("Renewal paperwork must be countersigned no later than September 30, 2026.", "September 30, 2026"),
    ("We can extend the multi-year discount of 12% if the seat count stays above 400.", "12%"),
    ("The uptime commitment in Section 4.2 remains 99.95% measured monthly.", "99.95%"),
    ("Service credits are capped at $25,000 per incident.", "$25,000"),
    ("Current deployment is 450 seats across three business units.", "450 seats"),
]

DISCLAIMER = ("This message and any attachments are confidential and intended solely for the "
              "addressee. If you have received this message in error, please notify the sender "
              "and delete it. Nothing in this message constitutes a binding offer unless "
              "executed in a definitive written agreement.")


def build_email_thread() -> str:
    bodies = [
        ("Rachel Kim <rkim@northstar-crm.example>", "Renewal terms — Meridian account",
         ["Hi Dev, good speaking this morning. Summarizing where we landed so nothing gets lost.",
          EM_FACTS[0][0], EM_FACTS[2][0],
          "Happy to walk your procurement team through the math whenever convenient."]),
        ("Dev Okonkwo <d.okonkwo@meridianrobotics.example>", "RE: Renewal terms — Meridian account",
         ["Thanks Rachel. Two clarifications before I socialize this internally.",
          EM_FACTS[5][0], "Does the discount survive if we consolidate units next year?",
          "Also please confirm the SLA language carries over unchanged."]),
        ("Rachel Kim <rkim@northstar-crm.example>", "RE: RE: Renewal terms — Meridian account",
         ["Confirming both points.", EM_FACTS[3][0], EM_FACTS[4][0],
          "The discount survives consolidation as long as aggregate seats stay above the threshold."]),
        ("Dev Okonkwo <d.okonkwo@meridianrobotics.example>", "RE: RE: RE: Renewal terms — Meridian account",
         ["Great. Last thing — timing. Our fiscal close makes October impossible.",
          EM_FACTS[1][0], "If that date is at risk we should talk this week."]),
        ("Rachel Kim <rkim@northstar-crm.example>", "RE: RE: RE: RE: Renewal terms — Meridian account",
         ["Understood on timing — that date is firm on our side too, so we are aligned.",
          "I'll send the DocuSign package tomorrow morning with everything reflected as above."]),
    ]
    thread = []
    quoted: list[str] = []
    for i, (sender, subject, paras) in enumerate(bodies):
        hdr = [f"From: {sender}", f"Subject: {subject}",
               f"Date: Mon, {13 + i} Jul 2026 0{9 + i}:1{i}:00 -0400", ""]
        fact_sentences = {f for f, _ in EM_FACTS}
        body_lines = []
        for p in paras:
            if p in fact_sentences:
                body_lines.append(p)  # keep fact sentences on one unwrapped line
            else:
                body_lines.extend(textwrap.wrap(p, width=76))
            body_lines.append("")
        body_lines.extend(["Best,", sender.split(" <")[0].split()[0], "", DISCLAIMER, ""])
        if quoted:
            body_lines.append("-----Original Message-----")
            body_lines.extend("> " + q for q in quoted)
        email = hdr + body_lines
        thread.append("\n".join(email))
        quoted = email
    return ("\n\n" + "=" * 76 + "\n\n").join(reversed(thread))


# ------------------------------------------------------------------ questions
def snippet_around(doc: str, value: str, width: int = 130) -> str:
    pos = doc.find(value)
    assert pos != -1, value
    lo = max(0, pos - width // 2)
    hi = min(len(doc), pos + len(value) + width // 2)
    while lo > 0 and not doc[lo - 1].isspace():
        lo -= 1
    while hi < len(doc) and not doc[hi].isspace():
        hi += 1
    snip = doc[lo:hi].strip()
    # widen until unique
    while doc.count(snip) > 1 and (lo > 0 or hi < len(doc)):
        lo = max(0, lo - 40)
        hi = min(len(doc), hi + 40)
        snip = doc[lo:hi].strip()
    return snip


REPORT_QS = [
    "What was consolidated revenue for fiscal 2025?",
    "How much was research and development expense?",
    "How many people did the Company employ at year end?",
    "What quarterly dividend did the Board declare per share?",
    "How large was the goodwill impairment charge?",
    "What was the effective tax rate for fiscal 2025?",
    "What was the order backlog at year end?",
    "What operating income did the Advanced Polymers segment report?",
]
TR_QS = [
    "What is the revised quarterly marketing budget?",
    "What date is the public launch locked for?",
    "What was monthly churn in June?",
    "How many backend engineers does Marcus say he needs?",
    "What was the Datadog quote for the new tier?",
    "What is NPS currently sitting at?",
    "What was trial-to-paid conversion last month?",
    "By what date must the security review be done?",
]
EM_QS = [
    "What is the total contract value for the 24-month term?",
    "By what date must renewal paperwork be countersigned?",
    "What multi-year discount percentage is on offer?",
    "What is the uptime commitment in Section 4.2?",
    "What are service credits capped at per incident?",
    "How many seats is the current deployment?",
]


def main() -> None:
    report = build_report()
    transcript = build_transcript()
    emails = build_email_thread()
    (DOCS / "hard_annual_report.txt").write_text(report, encoding="utf-8")
    (DOCS / "hard_transcript.txt").write_text(transcript, encoding="utf-8")
    (DOCS / "hard_email_thread.txt").write_text(emails, encoding="utf-8")

    questions = []
    for i, ((_, val), qtext) in enumerate(zip(REPORT_FACTS, REPORT_QS), 1):
        questions.append({"id": f"h-ar-{i}", "doc": "hard_annual_report.txt", "set": "hard",
                          "question": qtext, "expect_value": val,
                          "gt_quote": snippet_around(report, val)})
    for i, ((_, fact, val), qtext) in enumerate(zip(TR_FACTS, TR_QS), 1):
        questions.append({"id": f"h-tr-{i}", "doc": "hard_transcript.txt", "set": "hard",
                          "question": qtext, "expect_value": val, "gt_quote": fact})
    for i, ((_fact, val), qtext) in enumerate(zip(EM_FACTS, EM_QS), 1):
        # facts can be re-wrapped at 76 cols and re-quoted with '> ' — extract
        # the ground truth from the final document text, not the source string
        questions.append({"id": f"h-em-{i}", "doc": "hard_email_thread.txt", "set": "hard",
                          "question": qtext, "expect_value": val,
                          "gt_quote": snippet_around(emails, val)})

    out = ROOT / "corpus" / "questions_hard.json"
    out.write_text(json.dumps(questions, indent=1, ensure_ascii=False), encoding="utf-8")
    for name, text in (("report", report), ("transcript", transcript), ("emails", emails)):
        print(f"{name}: {len(text.split())} words, {len(text)} chars")
    print(f"{len(questions)} hard questions -> {out}")


if __name__ == "__main__":
    main()
