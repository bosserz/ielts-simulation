"""
Flask CLI commands.

Usage:
    flask seed-mock    — create a complete IELTS Academic Practice Test 1
    flask seed-teacher — create a default teacher account (dev only)
"""
import click
from flask.cli import with_appcontext
from .extensions import db


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _add_questions(section_id, rows):
    from .models.exam import Question
    from sqlalchemy import func
    max_order = db.session.query(func.max(Question.order_index)).filter_by(section_id=section_id).scalar() or 0
    for order, r in enumerate(rows, start=max_order + 1):
        opts = None
        if r.get("options"):
            opts = [{"id": k, "text": v} for k, v in r["options"].items()]
        db.session.add(Question(
            section_id=section_id,
            order_index=order,
            type=r["type"],
            prompt=r["prompt"],
            correct_answer=r.get("correct_answer"),
            options=opts,
            group_id=r.get("group_id"),
            marks=r.get("marks", 1),
        ))


# ---------------------------------------------------------------------------
# Passage texts (HTML)
# ---------------------------------------------------------------------------

_PASSAGE_1_TEXT = """
<h3>The Science of Urban Green Spaces</h3>

<p><strong>A</strong> Urban parks and green spaces have become increasingly important to city planners
and public health researchers in recent decades. Studies conducted across more than thirty cities worldwide
have consistently demonstrated that access to green spaces is associated with reduced rates of anxiety,
depression, and cardiovascular disease. A landmark 2019 study published in <em>Landscape and Urban
Planning</em> found that residents living within 300 metres of a public park reported 16% lower levels
of stress than those without nearby access.</p>

<p><strong>B</strong> The physical benefits of urban green spaces extend beyond mental health outcomes.
Research at Copenhagen University found that regular users of urban parks walked an average of 2.3 kilometres
more per week than non-users, contributing to measurable improvements in cardiovascular fitness. Green spaces
also act as natural air filters: mature trees absorb pollutants such as nitrogen dioxide and particulate matter,
with a single large tree capable of absorbing up to 150 grams of pollutants per day.</p>

<p><strong>C</strong> Despite these well-documented benefits, the distribution of urban green spaces is far from
equal. A 2021 analysis of 245 European cities found that affluent neighbourhoods contained on average 3.4 times
more green space per resident than lower-income areas. This disparity has led researchers to coin the term
"green gentrification" — a phenomenon in which the creation of new parks drives up property values, ultimately
displacing the lower-income communities they were designed to serve.</p>

<p><strong>D</strong> City planners have begun experimenting with alternative models to address this inequity.
In Singapore, vertical gardens and rooftop green spaces have been integrated into public housing estates,
providing green amenity without requiring additional land. Similarly, cities such as Melbourne and Vancouver
have adopted "urban forest strategies" that prioritise tree planting in underserved neighbourhoods, with
measurable progress in closing the green space gap.</p>

<p><strong>E</strong> The economic case for urban greening is also gaining traction among municipal governments.
Research from the University of Washington estimates that strategically placed street trees increase adjacent
property values by 3–15%, generating tax revenue that exceeds the cost of maintenance within fifteen years.
Furthermore, green spaces reduce urban "heat island" effects, lowering energy demand for air conditioning and
saving municipalities significant sums each summer.</p>

<p><strong>F</strong> Critics, however, question whether green space investment should be a priority when cities
face more pressing infrastructure deficits. They argue that the positive health effects attributed to parks may
be confounded by other variables — such as socioeconomic status, general neighbourhood quality, and prior health
conditions — and that the evidence base, while growing, remains methodologically mixed. Future research using
controlled longitudinal designs will be essential to resolve these debates and inform evidence-based urban policy.</p>
"""

_PASSAGE_2_TEXT = """
<h3>Artificial Intelligence in Modern Healthcare</h3>

<p><strong>A</strong> The integration of artificial intelligence into healthcare systems has accelerated
dramatically since 2015. Machine learning algorithms can now analyse medical images — X-rays, MRIs, and
histological slides — with a degree of accuracy that rivals, and in some cases surpasses, experienced
clinicians. A 2020 study in <em>Nature Medicine</em> found that a deep-learning system diagnosed diabetic
retinopathy from retinal photographs with 90.5% sensitivity, compared with 91.3% for ophthalmologists.
Such results have prompted widespread investment from both technology firms and healthcare providers.</p>

<p><strong>B</strong> Despite these impressive figures, the path from research to clinical deployment
remains fraught with difficulty. Many AI diagnostic tools perform well in controlled laboratory settings
but struggle when applied to the messier realities of clinical practice. Factors such as differences in
imaging equipment, patient demographics, and data quality across hospitals can cause algorithms trained
on one dataset to perform significantly worse when applied to another — a problem known as "domain shift."
This means that most AI tools require extensive local validation before they can be trusted in practice.</p>

<p><strong>C</strong> The regulatory landscape presents another significant challenge. Healthcare AI systems
must navigate a complex web of national and international regulations before they can be brought to market.
In the United States, the Food and Drug Administration has approved more than 500 AI-enabled medical devices
since 2017, but the approval process can take years. The European Union's AI Act, adopted in 2024, classifies
most medical AI as "high-risk," imposing stringent requirements for transparency, data governance, and
human oversight.</p>

<p><strong>D</strong> Equity concerns are increasingly prominent in discussions about healthcare AI.
Training datasets for many algorithms have historically overrepresented white, male, and higher-income
patient populations. When deployed on underrepresented groups, such algorithms can produce systematically
biased outputs — a problem that has already led to documented disparities in dermatology and cardiac care.
Addressing these biases requires deliberate effort in data collection, model design, and ongoing monitoring
after deployment.</p>

<p><strong>E</strong> Clinicians' attitudes towards AI vary widely. Some embrace diagnostic AI as a "second
opinion" that reduces cognitive load and catches errors they might otherwise miss. Others worry that
over-reliance on algorithmic recommendations will erode clinical reasoning skills over time and shift moral
responsibility away from the clinician in the event of an error. A 2022 survey of 1,400 physicians in twelve
countries found that 58% believed AI would improve diagnostic accuracy, but only 33% trusted AI systems enough
to act on their outputs without independent verification.</p>

<p><strong>F</strong> Looking ahead, the most transformative potential of healthcare AI may lie not in diagnosis
but in personalised treatment and drug discovery. AI platforms are already being used to identify novel drug
candidates at a fraction of the time and cost required by traditional approaches. In oncology, algorithms that
analyse genomic and proteomic data can predict with increasing accuracy which patients are likely to respond to
specific therapies, enabling precision medicine at scale. Whether these developments fulfil their promise will
depend on the quality of the underlying data, the robustness of regulatory frameworks, and the willingness of
clinical communities to embrace evidence-based change.</p>
"""

_PASSAGE_3_TEXT = """
<h3>The Future of Work in the Age of Automation</h3>

<p><strong>A</strong> Few topics generate as much anxiety in contemporary policy circles as the prospect of
widespread automation. Reports from organisations including the McKinsey Global Institute and the World Economic
Forum have estimated that between 15% and 30% of current jobs could be automated by 2030, with particular risk
concentrated among roles involving routine cognitive or physical tasks. Yet economists have long argued that
technological displacement historically creates as many jobs as it destroys — a proposition that is proving
difficult to verify with confidence in the current wave of AI-driven change.</p>

<p><strong>B</strong> Remote work, accelerated by the COVID-19 pandemic, has also fundamentally altered
employer expectations and worker preferences. A 2023 survey by the Pew Research Center found that 46% of
workers in roles compatible with remote working did so at least part of the time. Many employers report that
hybrid arrangements have increased productivity, but critics argue that the evidence is mixed and that
remote work exacerbates inequality between knowledge workers — who can work anywhere — and those in
service, manufacturing, or care roles who cannot.</p>

<p><strong>C</strong> The gig economy presents a further complication. Platforms such as Uber, Deliveroo, and
Upwork have created new forms of flexible employment that resist traditional classification. For some workers,
gig arrangements represent a valued source of autonomy; for others, they are a symptom of precarious
labour markets that offer no sick pay, pension contributions, or job security. Courts in several jurisdictions
have begun to reclassify gig workers as employees or "workers" with partial rights — a development that
platforms have fiercely resisted.</p>

<p><strong>D</strong> Education and retraining are widely seen as the primary tools for managing labour
market transitions. Governments in Singapore, Denmark, and Canada have invested heavily in "lifelong learning"
frameworks that offer subsidised retraining to displaced workers. However, evidence on the effectiveness
of such programmes is mixed: retraining works best when targeted at specific, in-demand skills in local
labour markets, and when combined with income support that allows workers the time to retrain meaningfully.
Generic skills programmes with no clear employment pathway have a poor track record.</p>

<p><strong>E</strong> Some researchers argue that the focus on job displacement obscures a more fundamental
question: what work is for. They contend that the goal should not be to preserve employment at all costs
but to ensure that the gains from automation are distributed broadly, through mechanisms such as shorter
working weeks, universal basic income, or expanded public services. Proponents of a four-day working week
point to trials in Iceland and the UK where output was maintained while worker wellbeing improved significantly.</p>

<p><strong>F</strong> What is clear is that the future of work will not be uniform. Outcomes will depend on
the policy choices governments make, the bargaining power of workers, the pace and direction of technological
change, and the capacity of educational institutions to adapt. Workers in countries with strong social safety
nets, active labour market policies, and high-quality public education are likely to navigate the transition
more successfully than those in labour markets characterised by flexibility without security. The challenge
for policymakers is to enable the gains from technological change without imposing the costs on those least
able to bear them.</p>
"""

# ---------------------------------------------------------------------------
# Question data
# ---------------------------------------------------------------------------

_MCQ_OPTS_AB = lambda a, b, c, d: {"A": a, "B": b, "C": c, "D": d}  # noqa: E731

_LISTENING_QUESTIONS = [
    # ── Part 1: Accommodation enquiry (Q 1–10) ─────────────────────────────
    {"type": "NOTE_COMPLETION", "group_id": "part-1",
     "prompt": "Type of accommodation required: ___________",
     "correct_answer": "studio flat"},
    {"type": "NOTE_COMPLETION", "group_id": "part-1",
     "prompt": "Maximum monthly rent (£): ___________",
     "correct_answer": "950"},
    {"type": "NOTE_COMPLETION", "group_id": "part-1",
     "prompt": "Preferred area of the city: ___________",
     "correct_answer": "Westfield"},
    {"type": "NOTE_COMPLETION", "group_id": "part-1",
     "prompt": "Applicant's full name: ___________",
     "correct_answer": "Chen Wei"},
    {"type": "NOTE_COMPLETION", "group_id": "part-1",
     "prompt": "Best contact number: ___________",
     "correct_answer": "07892 345617"},
    {"type": "NOTE_COMPLETION", "group_id": "part-1",
     "prompt": "Date available from: ___________",
     "correct_answer": "15th March"},
    {"type": "MCQ", "group_id": "part-1",
     "prompt": "Why does the applicant prefer a studio flat?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_AB("It is less expensive", "It suits a single person living alone",
                              "It is easier to find", "It is closer to university")},
    {"type": "MCQ", "group_id": "part-1",
     "prompt": "What does the letting agency say about the Westfield area?",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB("It has no available properties", "It is the most expensive area",
                              "It has good transport links", "It is too far from the city centre")},
    {"type": "MCQ", "group_id": "part-1",
     "prompt": "What additional feature does the applicant request?",
     "correct_answer": "A",
     "options": _MCQ_OPTS_AB("A parking space", "A garden", "A second bedroom", "A home office")},
    {"type": "MCQ", "group_id": "part-1",
     "prompt": "What will the agency send the applicant?",
     "correct_answer": "D",
     "options": _MCQ_OPTS_AB("A printed brochure", "A map of available properties",
                              "A list of landlords", "An email with matching properties")},

    # ── Part 2: Community centre tour (Q 11–20) ────────────────────────────
    {"type": "MCQ", "group_id": "part-2",
     "prompt": "The new fitness suite is located on which floor?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_AB("Ground floor", "First floor", "Second floor", "Basement")},
    {"type": "MCQ", "group_id": "part-2",
     "prompt": "The community café opens at what time on weekdays?",
     "correct_answer": "A",
     "options": _MCQ_OPTS_AB("8:00 am", "9:00 am", "9:30 am", "10:00 am")},
    {"type": "MCQ", "group_id": "part-2",
     "prompt": "Which room has recently been renovated?",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB("The sports hall", "The library", "The dance studio", "The meeting room")},
    {"type": "MCQ", "group_id": "part-2",
     "prompt": "How much does annual membership cost?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_AB("£45", "£60", "£75", "£90")},
    {"type": "MCQ", "group_id": "part-2",
     "prompt": "What is offered free of charge to under-18s?",
     "correct_answer": "D",
     "options": _MCQ_OPTS_AB("Gym access", "Swimming lessons", "Cooking classes", "After-school club")},
    {"type": "SENTENCE_COMPLETION", "group_id": "part-2",
     "prompt": "The centre plans to open a new ___________ facility in the spring.",
     "correct_answer": "outdoor climbing"},
    {"type": "SENTENCE_COMPLETION", "group_id": "part-2",
     "prompt": "Classes for adults are held on ___________ evenings.",
     "correct_answer": "Tuesday and Thursday"},
    {"type": "SENTENCE_COMPLETION", "group_id": "part-2",
     "prompt": "The car park can accommodate up to ___________ vehicles.",
     "correct_answer": "120"},
    {"type": "SENTENCE_COMPLETION", "group_id": "part-2",
     "prompt": "Members receive a ___________ discount at the café.",
     "correct_answer": "10%"},
    {"type": "SENTENCE_COMPLETION", "group_id": "part-2",
     "prompt": "The centre's website address is ___________.",
     "correct_answer": "www.northsidecc.org.uk"},

    # ── Part 3: Research assignment discussion (Q 21–30) ───────────────────
    {"type": "MCQ", "group_id": "part-3",
     "prompt": "What is the main topic of the students' research project?",
     "correct_answer": "A",
     "options": _MCQ_OPTS_AB("The impact of social media on academic performance",
                              "Online learning in secondary schools",
                              "The use of smartphones in lectures",
                              "Digital literacy among university students")},
    {"type": "MCQ", "group_id": "part-3",
     "prompt": "Why does Marcus suggest using a survey rather than interviews?",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB("It is more reliable", "It requires less preparation",
                              "It will reach more participants quickly", "The tutor recommended it")},
    {"type": "MCQ", "group_id": "part-3",
     "prompt": "What does Priya say about the secondary sources they found?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_AB("Most are too recent to be reliable",
                              "Some are not from peer-reviewed journals",
                              "They are mostly from overseas studies",
                              "They contradict each other")},
    {"type": "MCQ", "group_id": "part-3",
     "prompt": "The students agree to submit a draft to their tutor by:",
     "correct_answer": "D",
     "options": _MCQ_OPTS_AB("This Friday", "Next Monday", "Next Wednesday", "Next Friday")},
    {"type": "MCQ", "group_id": "part-3",
     "prompt": "What aspect of their topic will Marcus focus on in his section?",
     "correct_answer": "A",
     "options": _MCQ_OPTS_AB("Positive effects of social media on learning",
                              "Negative effects on concentration",
                              "Historical background of the internet",
                              "Comparison of different social media platforms")},
    {"type": "NOTE_COMPLETION", "group_id": "part-3",
     "prompt": "The project counts for ___________% of the final module grade.",
     "correct_answer": "40"},
    {"type": "NOTE_COMPLETION", "group_id": "part-3",
     "prompt": "They need a minimum of ___________ survey respondents.",
     "correct_answer": "50"},
    {"type": "NOTE_COMPLETION", "group_id": "part-3",
     "prompt": "The tutor's office hour is on ___________ at 2 pm.",
     "correct_answer": "Thursday"},
    {"type": "NOTE_COMPLETION", "group_id": "part-3",
     "prompt": "The word limit for the written report is ___________ words.",
     "correct_answer": "3000"},
    {"type": "NOTE_COMPLETION", "group_id": "part-3",
     "prompt": "They will use ___________ to share documents between them.",
     "correct_answer": "Google Drive"},

    # ── Part 4: Renewable energy lecture (Q 31–40) ─────────────────────────
    {"type": "NOTE_COMPLETION", "group_id": "part-4",
     "prompt": "Solar power currently accounts for approximately ___________% of global electricity generation.",
     "correct_answer": "5"},
    {"type": "NOTE_COMPLETION", "group_id": "part-4",
     "prompt": "The cost of solar panels has fallen by over ___________% since 2010.",
     "correct_answer": "89"},
    {"type": "NOTE_COMPLETION", "group_id": "part-4",
     "prompt": "The largest offshore wind farm in the world is located off the coast of ___________.",
     "correct_answer": "Yorkshire"},
    {"type": "NOTE_COMPLETION", "group_id": "part-4",
     "prompt": "Hydrogen produced using renewable electricity is called ___________ hydrogen.",
     "correct_answer": "green"},
    {"type": "NOTE_COMPLETION", "group_id": "part-4",
     "prompt": "The main challenge of intermittent renewables is the need for large-scale ___________.",
     "correct_answer": "energy storage"},
    {"type": "NOTE_COMPLETION", "group_id": "part-4",
     "prompt": "Grid-scale batteries currently store energy for a maximum of approximately ___________ hours.",
     "correct_answer": "four"},
    {"type": "TABLE_COMPLETION", "group_id": "part-4",
     "prompt": "Country with the highest share of wind power in its electricity mix: ___________",
     "correct_answer": "Denmark"},
    {"type": "TABLE_COMPLETION", "group_id": "part-4",
     "prompt": "Technology described as the 'holy grail' of clean energy: ___________",
     "correct_answer": "nuclear fusion"},
    {"type": "TABLE_COMPLETION", "group_id": "part-4",
     "prompt": "The International Energy Agency's target year for net-zero electricity globally: ___________",
     "correct_answer": "2035"},
    {"type": "TABLE_COMPLETION", "group_id": "part-4",
     "prompt": "Main policy mechanism used by the EU to drive clean energy investment: ___________",
     "correct_answer": "carbon pricing"},
]

_READING_P1_QUESTIONS = [
    # Q1–6 True/False/Not Given
    {"type": "TFNG", "group_id": "passage-1",
     "prompt": "Studies in more than thirty cities have linked proximity to parks with lower stress levels.",
     "correct_answer": "True"},
    {"type": "TFNG", "group_id": "passage-1",
     "prompt": "The Copenhagen University research found that park users walked more than 3 kilometres extra per week.",
     "correct_answer": "False"},
    {"type": "TFNG", "group_id": "passage-1",
     "prompt": "The 2021 analysis included cities from every continent.",
     "correct_answer": "Not Given"},
    {"type": "TFNG", "group_id": "passage-1",
     "prompt": "Green gentrification refers to a process that can displace lower-income residents.",
     "correct_answer": "True"},
    {"type": "TFNG", "group_id": "passage-1",
     "prompt": "Singapore's vertical garden programme is funded by the national government.",
     "correct_answer": "Not Given"},
    {"type": "TFNG", "group_id": "passage-1",
     "prompt": "The University of Washington study found that tree planting generates more revenue than it costs within fifteen years.",
     "correct_answer": "True"},
    # Q7–13 Short Answer
    {"type": "SHORT_ANSWER", "group_id": "passage-1",
     "prompt": "How much more green space per resident do affluent neighbourhoods have compared to lower-income areas? (Write NO MORE THAN THREE WORDS AND/OR A NUMBER)",
     "correct_answer": "3.4 times"},
    {"type": "SHORT_ANSWER", "group_id": "passage-1",
     "prompt": "What term describes the phenomenon where park creation raises property values and displaces local residents?",
     "correct_answer": "green gentrification"},
    {"type": "SHORT_ANSWER", "group_id": "passage-1",
     "prompt": "In which city have vertical gardens been added to public housing estates?",
     "correct_answer": "Singapore"},
    {"type": "SHORT_ANSWER", "group_id": "passage-1",
     "prompt": "By what percentage range can street trees increase adjacent property values, according to the University of Washington?",
     "correct_answer": "3-15%"},
    {"type": "SHORT_ANSWER", "group_id": "passage-1",
     "prompt": "What effect do green spaces reduce, which lowers summer energy costs for cities?",
     "correct_answer": "heat island"},
    {"type": "SHORT_ANSWER", "group_id": "passage-1",
     "prompt": "What type of research design do critics say is needed to resolve debates about green space benefits? (Write NO MORE THAN THREE WORDS)",
     "correct_answer": "controlled longitudinal"},
    {"type": "SHORT_ANSWER", "group_id": "passage-1",
     "prompt": "By what percentage were stress levels lower among residents living within 300 metres of a park?",
     "correct_answer": "16%"},
]

_MATCHING_HEADINGS_OPTS = {
    "A": "i. Achieving fairer outcomes for all patient groups",
    "B": "ii. The gap between laboratory success and real-world application",
    "C": "iii. The potential for transforming drug development",
    "D": "iv. Regulating a rapidly evolving technology",
    "E": "v. The role of AI in reducing medical errors",
    "F": "vi. The widespread adoption of AI diagnostic tools",
    "G": "vii. Clinician scepticism and professional concerns",
    "H": "viii. Long-standing bias in medical research data",
}

_READING_P2_QUESTIONS = [
    # Q14–19 Matching Headings (Paragraphs A–F)
    {"type": "MATCHING_HEADINGS", "group_id": "passage-2",
     "prompt": "Paragraph A",
     "correct_answer": "F",
     "options": _MATCHING_HEADINGS_OPTS},
    {"type": "MATCHING_HEADINGS", "group_id": "passage-2",
     "prompt": "Paragraph B",
     "correct_answer": "B",
     "options": _MATCHING_HEADINGS_OPTS},
    {"type": "MATCHING_HEADINGS", "group_id": "passage-2",
     "prompt": "Paragraph C",
     "correct_answer": "D",
     "options": _MATCHING_HEADINGS_OPTS},
    {"type": "MATCHING_HEADINGS", "group_id": "passage-2",
     "prompt": "Paragraph D",
     "correct_answer": "A",
     "options": _MATCHING_HEADINGS_OPTS},
    {"type": "MATCHING_HEADINGS", "group_id": "passage-2",
     "prompt": "Paragraph E",
     "correct_answer": "G",
     "options": _MATCHING_HEADINGS_OPTS},
    {"type": "MATCHING_HEADINGS", "group_id": "passage-2",
     "prompt": "Paragraph F",
     "correct_answer": "C",
     "options": _MATCHING_HEADINGS_OPTS},
    # Q20–26 Multiple Choice
    {"type": "MCQ", "group_id": "passage-2",
     "prompt": "What was the AI system's sensitivity for diagnosing diabetic retinopathy?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_AB("89.5%", "90.5%", "91.3%", "92.0%")},
    {"type": "MCQ", "group_id": "passage-2",
     "prompt": "What term describes an algorithm performing worse when applied to different hospital data than the data it was trained on?",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB("data drift", "algorithmic bias", "domain shift", "overfitting")},
    {"type": "MCQ", "group_id": "passage-2",
     "prompt": "How many AI-enabled medical devices has the FDA approved since 2017?",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB("More than 300", "More than 400", "More than 500", "More than 600")},
    {"type": "MCQ", "group_id": "passage-2",
     "prompt": "Under the EU AI Act, most medical AI is classified as:",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB("low-risk", "moderate-risk", "high-risk", "critical-risk")},
    {"type": "MCQ", "group_id": "passage-2",
     "prompt": "What percentage of surveyed physicians believed AI would improve diagnostic accuracy?",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB("33%", "45%", "58%", "72%")},
    {"type": "MCQ", "group_id": "passage-2",
     "prompt": "In which medical field have AI bias issues already led to documented disparities?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_AB("radiology", "dermatology", "neurology", "cardiothoracic surgery")},
    {"type": "MCQ", "group_id": "passage-2",
     "prompt": "According to the text, where may the most transformative potential of healthcare AI lie?",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB("emergency medicine", "medical imaging",
                              "personalised treatment and drug discovery",
                              "surgical robotics")},
]

_READING_P3_QUESTIONS = [
    # Q27–32 Yes/No/Not Given
    {"type": "YNGNG", "group_id": "passage-3",
     "prompt": "The author believes that automation will inevitably destroy more jobs than it creates.",
     "correct_answer": "No"},
    {"type": "YNGNG", "group_id": "passage-3",
     "prompt": "The Pew Research Center survey showed that almost half of eligible remote workers worked remotely at least part of the time in 2023.",
     "correct_answer": "Yes"},
    {"type": "YNGNG", "group_id": "passage-3",
     "prompt": "Gig workers are better paid than equivalent full-time employees.",
     "correct_answer": "Not Given"},
    {"type": "YNGNG", "group_id": "passage-3",
     "prompt": "The writer implies that generic retraining programmes without a clear employment pathway are ineffective.",
     "correct_answer": "Yes"},
    {"type": "YNGNG", "group_id": "passage-3",
     "prompt": "The writer supports a universal basic income as the best response to automation.",
     "correct_answer": "Not Given"},
    {"type": "YNGNG", "group_id": "passage-3",
     "prompt": "Workers in countries with strong social safety nets are likely to manage labour market change better.",
     "correct_answer": "Yes"},
    # Q33–40 Sentence Completion
    {"type": "SENTENCE_COMPLETION", "group_id": "passage-3",
     "prompt": "Estimates from major research organisations suggest that between 15% and 30% of jobs could be automated by ___________.",
     "correct_answer": "2030"},
    {"type": "SENTENCE_COMPLETION", "group_id": "passage-3",
     "prompt": "Critics of remote work argue that it increases inequality between knowledge workers and those in ___________, manufacturing, or care roles.",
     "correct_answer": "service"},
    {"type": "SENTENCE_COMPLETION", "group_id": "passage-3",
     "prompt": "Courts in several countries have begun to reclassify gig workers as employees or '___________ ' with partial rights.",
     "correct_answer": "workers"},
    {"type": "SENTENCE_COMPLETION", "group_id": "passage-3",
     "prompt": "Effective retraining programmes work best when targeted at specific skills and combined with ___________ support.",
     "correct_answer": "income"},
    {"type": "SENTENCE_COMPLETION", "group_id": "passage-3",
     "prompt": "Proponents of the four-day working week cite trials in Iceland and the ___________ as evidence that output can be maintained.",
     "correct_answer": "UK"},
    {"type": "SENTENCE_COMPLETION", "group_id": "passage-3",
     "prompt": "The passage argues that workers in countries with high-quality public ___________ will navigate automation more successfully.",
     "correct_answer": "education"},
    {"type": "SENTENCE_COMPLETION", "group_id": "passage-3",
     "prompt": "Singapore, Denmark, and Canada have invested in '___________ learning' frameworks to help displaced workers.",
     "correct_answer": "lifelong"},
    {"type": "SENTENCE_COMPLETION", "group_id": "passage-3",
     "prompt": "The final paragraph states that policymakers must enable the gains from technological change without imposing costs on those least able to ___________ them.",
     "correct_answer": "bear"},
]

# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

@click.command("seed-mock")
@with_appcontext
def seed_mock_command():
    """Create IELTS Academic Practice Test 1 with all sections and questions."""
    from .models.exam import (
        Exam, Section, ExamType, ExamStatus, SectionType,
    )
    from .models.user import User, UserRole

    if Exam.query.filter_by(title="IELTS Academic Practice Test 1").first():
        click.echo("Mock exam already exists — skipping. Delete it first to re-seed.")
        return

    teacher = User.query.filter_by(role=UserRole.TEACHER).first()
    if not teacher:
        click.echo("No teacher account found. Run 'flask seed-teacher' first.")
        return

    # ── Exam ──────────────────────────────────────────────────────────────
    exam = Exam(
        title="IELTS Academic Practice Test 1",
        type=ExamType.ACADEMIC,
        status=ExamStatus.PUBLISHED,
        created_by=teacher.id,
    )
    db.session.add(exam)
    db.session.flush()

    # ── Listening (30 min, 4 parts) ───────────────────────────────────────
    listening = Section(
        exam_id=exam.id,
        type=SectionType.LISTENING,
        order_index=1,
        time_limit_s=30 * 60,
        config={
            "parts": [
                {"audioFileKey": "listening/pt1-part1.mp3",
                 "label": "Part 1 (Questions 1–10)", "groupId": "part-1"},
                {"audioFileKey": "listening/pt1-part2.mp3",
                 "label": "Part 2 (Questions 11–20)", "groupId": "part-2"},
                {"audioFileKey": "listening/pt1-part3.mp3",
                 "label": "Part 3 (Questions 21–30)", "groupId": "part-3"},
                {"audioFileKey": "listening/pt1-part4.mp3",
                 "label": "Part 4 (Questions 31–40)", "groupId": "part-4"},
            ]
        },
    )
    db.session.add(listening)
    db.session.flush()
    _add_questions(listening.id, _LISTENING_QUESTIONS)

    # ── Reading (60 min, 3 passages) ──────────────────────────────────────
    reading = Section(
        exam_id=exam.id,
        type=SectionType.READING,
        order_index=2,
        time_limit_s=60 * 60,
        config={
            "passages": [
                {"title": "Passage 1 — Urban Green Spaces",
                 "text": _PASSAGE_1_TEXT.strip(),
                 "groupId": "passage-1"},
                {"title": "Passage 2 — AI in Healthcare",
                 "text": _PASSAGE_2_TEXT.strip(),
                 "groupId": "passage-2"},
                {"title": "Passage 3 — The Future of Work",
                 "text": _PASSAGE_3_TEXT.strip(),
                 "groupId": "passage-3"},
            ]
        },
    )
    db.session.add(reading)
    db.session.flush()
    _add_questions(reading.id, _READING_P1_QUESTIONS)
    _add_questions(reading.id, _READING_P2_QUESTIONS)
    _add_questions(reading.id, _READING_P3_QUESTIONS)

    # ── Writing (60 min) ──────────────────────────────────────────────────
    writing = Section(
        exam_id=exam.id,
        type=SectionType.WRITING,
        order_index=3,
        time_limit_s=60 * 60,
        config={
            "task1Prompt": (
                "<p>The bar chart below shows the average number of hours per day that adults in "
                "five countries spent on social media in 2015, 2019, and 2023.</p>"
                "<p><em>Summarise the information by selecting and reporting the main features, "
                "and make comparisons where relevant.</em></p>"
                "<p>Write at least <strong>150 words</strong>.</p>"
            ),
            "task2Prompt": (
                "<p>Some people believe that the increasing use of technology in the workplace "
                "has made employees less productive, while others argue the opposite.</p>"
                "<p><em>Discuss both views and give your own opinion.</em></p>"
                "<p>Write at least <strong>250 words</strong>.</p>"
            ),
        },
    )
    db.session.add(writing)

    # ── Speaking (14 min) ─────────────────────────────────────────────────
    speaking = Section(
        exam_id=exam.id,
        type=SectionType.SPEAKING,
        order_index=4,
        time_limit_s=14 * 60,
        config={
            "parts": [
                {
                    "question": (
                        "Part 1 — Introduction & Interview\n\n"
                        "Let's talk about where you live.\n"
                        "• Can you describe the area where you currently live?\n"
                        "• What do you like most about your neighbourhood?\n"
                        "• How has your local area changed in recent years?\n\n"
                        "Now let's talk about your free time.\n"
                        "• What do you usually do in the evenings?\n"
                        "• Do you prefer spending time indoors or outdoors? Why?"
                    )
                },
                {
                    "question": (
                        "Part 2 — Long Turn (Cue Card)\n\n"
                        "Describe a journey that had a significant impact on you.\n\n"
                        "You should say:\n"
                        "• where you went\n"
                        "• why you made the journey\n"
                        "• what happened during the journey\n\n"
                        "and explain why this journey was important to you.\n\n"
                        "You have one minute to prepare. Then speak for one to two minutes."
                    )
                },
                {
                    "question": (
                        "Part 3 — Discussion\n\n"
                        "Let's discuss travel and its effects on people and societies.\n"
                        "• Do you think international travel has become too easy and too frequent? Why?\n"
                        "• How does tourism affect the culture of the places people visit?\n"
                        "• Some people say that virtual reality will eventually replace the need for "
                        "physical travel. Do you agree?\n"
                        "• What responsibilities do travellers have towards the environments they visit?"
                    )
                },
            ]
        },
    )
    db.session.add(speaking)
    db.session.commit()

    click.echo(
        "Created: IELTS Academic Practice Test 1\n"
        f"  Listening : 40 questions across 4 parts\n"
        f"  Reading   : 40 questions across 3 passages\n"
        f"  Writing   : 2 tasks (Task 1 + Task 2)\n"
        f"  Speaking  : 3 parts\n"
        "Status: PUBLISHED"
    )


@click.command("seed-teacher")
@with_appcontext
def seed_teacher_command():
    """Create a default teacher account for development."""
    import bcrypt
    from .models.user import User, UserRole

    email = "teacher@intsight.co"
    if User.query.filter_by(email=email).first():
        click.echo(f"Teacher account '{email}' already exists.")
        return

    pw_hash = bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode()
    teacher = User(name="Intsight Teacher", email=email,
                   password_hash=pw_hash, role=UserRole.TEACHER)
    db.session.add(teacher)
    db.session.commit()
    click.echo(f"Created teacher account: {email} / admin1234")


@click.command("create-admin")
@click.option("--name", prompt="Name", help="Admin's display name")
@click.option("--email", prompt="Email", help="Admin's email address")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Password")
@with_appcontext
def create_admin_command(name, email, password):
    """Create a teacher/admin account with a custom email and password."""
    import bcrypt
    from .models.user import User, UserRole

    if User.query.filter_by(email=email).first():
        click.echo(f"An account with email '{email}' already exists.")
        return

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(name=name, email=email, password_hash=pw_hash, role=UserRole.TEACHER)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Admin account created: {email}")


# ---------------------------------------------------------------------------
# Practice Test 2 — passage texts
# ---------------------------------------------------------------------------

_PASSAGE_FUNGI_TEXT = """
<h3>The Hidden Intelligence of Fungi</h3>

<p>For many years, fungi were treated as simple organisms that existed mainly to decompose dead material.
They appeared in textbooks as mushrooms, moulds, or invisible agents of decay. However, modern research
has shown that fungi are far more complex than previously assumed. They play essential roles in ecosystems,
agriculture, medicine, and even communication between plants.</p>

<p>Fungi are neither plants nor animals. They belong to their own biological kingdom. Unlike plants, fungi
do not produce energy through photosynthesis. Instead, they absorb nutrients from their surroundings.
The main body of many fungi is not the mushroom visible above ground, but a network of thin threads called
mycelium. These threads can spread through soil, wood, or other organic matter, forming vast underground
networks.</p>

<p>One of the most important functions of fungi is decomposition. By breaking down dead plants and animals,
fungi recycle nutrients back into the environment. Without them, forests would be covered with dead material,
and essential elements such as carbon, nitrogen, and phosphorus would remain locked inside organic matter.
Fungi therefore support the nutrient cycles that allow new life to grow.</p>

<p>Fungi also form partnerships with plants. Many plants have roots connected to fungal networks in
relationships known as mycorrhizae. In these partnerships, fungi help plants absorb water and minerals,
especially phosphorus. In return, plants provide fungi with sugars produced through photosynthesis.
This exchange is not always equal, but it is often mutually beneficial. Some scientists have described
these underground networks as a kind of "wood wide web," because they can connect multiple plants in a
shared system.</p>

<p>There is growing evidence that fungal networks may help plants respond to environmental stress. For
example, when one plant is attacked by insects, chemical signals may travel through fungal networks and
prepare nearby plants to defend themselves. However, scientists remain cautious. It is tempting to describe
fungal networks as intelligent or cooperative, but such language can be misleading. Fungi do not think like
humans. Their behaviour results from chemical processes and evolutionary adaptation.</p>

<p>Fungi have also had an enormous impact on medicine. The discovery of penicillin, an antibiotic produced
by a type of mould, transformed modern healthcare by making bacterial infections far more treatable. Other
fungal compounds are used in drugs that suppress the immune system, lower cholesterol, or treat certain
diseases. At the same time, fungi can also be harmful. Some cause infections in humans, especially in people
with weakened immune systems. Others damage crops, leading to serious agricultural losses.</p>

<p>In agriculture, fungi present both opportunities and risks. Beneficial fungi can improve soil health and
reduce the need for chemical fertilisers. Some farmers use fungal products to increase plant growth or protect
crops from disease. On the other hand, fungal pathogens can spread quickly and destroy harvests. Climate
change may increase this risk by allowing certain fungal species to survive in new regions.</p>

<p>The study of fungi is expanding rapidly. Scientists are investigating their potential in sustainable
materials, food production, environmental cleanup, and carbon storage. Mycelium-based materials, for example,
can be grown into packaging or construction products that may replace plastics or foams. Some fungi can even
break down pollutants in contaminated soil.</p>

<p>Despite their importance, fungi remain under-studied compared with plants and animals. Many fungal
species have not yet been identified. As researchers learn more, fungi are increasingly seen not as simple
background organisms, but as active participants in the systems that support life on Earth.</p>
"""

_PASSAGE_SILK_ROAD_TEXT = """
<h3>The Silk Road: Trade, Culture, and Connection</h3>

<p>The Silk Road was not a single road, but a network of trade routes connecting East Asia, Central Asia,
the Middle East, and Europe. It developed over many centuries and became one of the most important systems
of exchange in world history. Although silk was one of its most famous goods, the Silk Road carried much
more than luxury fabric. It transported ideas, religions, technologies, languages, artistic styles,
and diseases.</p>

<p>The origins of the Silk Road are often associated with China's Han dynasty, especially during the second
century BCE. Chinese envoys travelled westward to form alliances and gather information about neighbouring
regions. Over time, these journeys helped open trade connections between China and Central Asia. Merchants,
however, rarely travelled the entire route from China to Europe. Instead, goods usually passed through many
hands, moving from one market town to another.</p>

<p>Silk was highly valued in Rome and other parts of the ancient world because it was light, beautiful, and
difficult to produce. For centuries, China carefully protected the knowledge of silk production. In return,
China received horses, glassware, precious metals, and other goods from western regions. Central Asian cities
became important trading centres because they linked different cultural and economic zones.</p>

<p>One of the most significant effects of the Silk Road was cultural exchange. Buddhism spread from India
into Central Asia and China partly through these trade routes. Monks, translators, and pilgrims travelled
alongside merchants, carrying religious texts and artistic traditions. Over time, Buddhist ideas were adapted
to local cultures, producing new forms of art and worship.</p>

<p>The Silk Road also supported the movement of technologies. Papermaking, which began in China, eventually
spread westward and transformed education, administration, and literature. Other innovations, including
certain agricultural techniques and military technologies, also travelled across regions. These exchanges
were not always direct or immediate; they often occurred gradually through contact among traders, scholars,
and craftsmen.</p>

<p>However, the Silk Road was not only a story of peaceful exchange. Trade routes could be dangerous.
Merchants faced deserts, mountains, bandits, political instability, and harsh weather. Empires competed to
control key sections of the routes because trade could generate wealth and political influence. When large
empires provided security, long-distance trade usually increased. When political order collapsed, trade
became more difficult.</p>

<p>Disease also moved along trade networks. Some historians argue that the spread of the Black Death in the
fourteenth century was connected to trade routes across Eurasia. The same networks that helped goods and
ideas travel could also allow pathogens to move between populations.</p>

<p>The importance of the Silk Road declined after maritime trade expanded. Sea routes became increasingly
attractive because ships could carry larger quantities of goods at lower cost. European exploration and the
growth of oceanic trade gradually shifted global commerce away from overland routes. Nevertheless, the Silk
Road remained historically significant because it connected distant societies and shaped global development.</p>

<p>Today, the term "Silk Road" is often used symbolically to describe international connection and exchange.
Modern infrastructure projects sometimes refer to the Silk Road to evoke this history of trade and cultural
contact. Yet the historical Silk Road should not be imagined as a simple highway. It was a changing network
shaped by geography, politics, technology, and human ambition.</p>
"""

# ---------------------------------------------------------------------------
# Practice Test 2 — question data
# ---------------------------------------------------------------------------

_MCQ_OPTS_ABC = lambda a, b, c: {"A": a, "B": b, "C": c}  # noqa: E731

_LISTENING_PT2_QUESTIONS = [
    # ── Part 1: Student registration (Q 1–10) ─────────────────────────────
    {"type": "NOTE_COMPLETION", "group_id": "pt2-part-1",
     "prompt": "Student ID: ___________",
     "correct_answer": "ST49271"},
    {"type": "NOTE_COMPLETION", "group_id": "pt2-part-1",
     "prompt": "Programme — Bachelor of ___________",
     "correct_answer": "International Studies"},
    {"type": "NOTE_COMPLETION", "group_id": "pt2-part-1",
     "prompt": "Problem course: ___________",
     "correct_answer": "Introduction to Political Economy"},
    {"type": "NOTE_COMPLETION", "group_id": "pt2-part-1",
     "prompt": "Course code: ___________",
     "correct_answer": "POL 104"},
    {"type": "NOTE_COMPLETION", "group_id": "pt2-part-1",
     "prompt": "Expected processing time for override: ___________",
     "correct_answer": "24 hours"},
    {"type": "MCQ", "group_id": "pt2-part-1",
     "prompt": "Why was Leda unable to register for Introduction to Political Economy?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_ABC(
         "The course was already full",
         "The system showed an incorrect prerequisite",
         "He had not paid his tuition fee")},
    {"type": "MCQ", "group_id": "pt2-part-1",
     "prompt": "What is true about Environmental Policy?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_ABC(
         "It is not approved for Leda's degree",
         "It requires a Saturday field trip",
         "It is only available to second-year students")},
    {"type": "MCQ", "group_id": "pt2-part-1",
     "prompt": "Leda decides that Global Media and Society is better because",
     "correct_answer": "C",
     "options": _MCQ_OPTS_ABC(
         "it has no final exam",
         "it is taught by a famous professor",
         "it does not conflict with her Saturday work")},
    {"type": "MCQ", "group_id": "pt2-part-1",
     "prompt": "When does the add-drop period end?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_ABC("September 8th", "September 12th", "October 10th")},
    {"type": "MCQ", "group_id": "pt2-part-1",
     "prompt": "What must Leda maintain to remain a full-time student?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_ABC(
         "At least 9 credits",
         "At least 12 credits",
         "At least 15 credits")},

    # ── Part 2: Geopolitics lecture (Q 11–20) ─────────────────────────────
    {"type": "SENTENCE_COMPLETION", "group_id": "pt2-part-2",
     "prompt": "Geopolitics studies the relationship between geography, political power, economic interests, and ___________.",
     "correct_answer": "international relations"},
    {"type": "SENTENCE_COMPLETION", "group_id": "pt2-part-2",
     "prompt": "Geography creates both opportunities and ___________.",
     "correct_answer": "constraints"},
    {"type": "SENTENCE_COMPLETION", "group_id": "pt2-part-2",
     "prompt": "The Strait of Malacca connects the Indian Ocean and the ___________.",
     "correct_answer": "Pacific Ocean"},
    {"type": "SENTENCE_COMPLETION", "group_id": "pt2-part-2",
     "prompt": "Rare earth minerals, lithium, and cobalt are important for modern ___________.",
     "correct_answer": "technology"},
    {"type": "SENTENCE_COMPLETION", "group_id": "pt2-part-2",
     "prompt": "Digital infrastructure includes undersea internet cables, satellite networks, data centres, and ___________ systems.",
     "correct_answer": "cloud computing"},
    {"type": "Tfng", "group_id": "pt2-part-2",
     "prompt": "The professor says geography completely determines the future of a country.",
     "correct_answer": "False"},
    {"type": "Tfng", "group_id": "pt2-part-2",
     "prompt": "The Strait of Malacca is important because large amounts of global trade pass through it.",
     "correct_answer": "True"},
    {"type": "Tfng", "group_id": "pt2-part-2",
     "prompt": "Border disputes are always caused by natural boundaries such as rivers and mountains.",
     "correct_answer": "False"},
    {"type": "Tfng", "group_id": "pt2-part-2",
     "prompt": "Climate change may create new shipping routes in the Arctic.",
     "correct_answer": "True"},
    {"type": "Tfng", "group_id": "pt2-part-2",
     "prompt": "The professor believes only large countries can influence geopolitics.",
     "correct_answer": "False"},
]

_READING_FUNGI_QUESTIONS = [
    # Q1–4 Multiple Choice (4 options)
    {"type": "MCQ", "group_id": "pt2-passage-1",
     "prompt": "What is the main idea of the passage?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_AB(
         "Fungi are dangerous organisms that mainly harm crops",
         "Fungi are complex organisms with important ecological and practical roles",
         "Fungi should be classified as plants because they live in soil",
         "Fungi are useful only because they produce antibiotics")},
    {"type": "MCQ", "group_id": "pt2-passage-1",
     "prompt": "The main body of many fungi is",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB(
         "the mushroom above ground",
         "a plant root",
         "a mycelium network",
         "a photosynthetic stem")},
    {"type": "MCQ", "group_id": "pt2-passage-1",
     "prompt": "What do fungi receive from plants in mycorrhizal relationships?",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB("Phosphorus", "Water", "Sugars", "Nitrogen")},
    {"type": "MCQ", "group_id": "pt2-passage-1",
     "prompt": "Why are scientists cautious about calling fungal networks \"intelligent\"?",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB(
         "Fungi cannot communicate in any way",
         "Fungi are not useful to ecosystems",
         "Fungal behaviour comes from chemical and evolutionary processes",
         "Fungal networks exist only in laboratories")},
    # Q5–7 Summary Completion
    {"type": "SUMMARY_COMPLETION", "group_id": "pt2-passage-1",
     "prompt": (
         "Fungi are essential in ecosystems because they break down dead organisms and return "
         "nutrients to the environment. This process supports important 5. ___________."),
     "correct_answer": "nutrient cycles"},
    {"type": "SUMMARY_COMPLETION", "group_id": "pt2-passage-1",
     "prompt": (
         "Many fungi also live in partnership with plant roots in relationships called "
         "6. ___________."),
     "correct_answer": "mycorrhizae"},
    {"type": "SUMMARY_COMPLETION", "group_id": "pt2-passage-1",
     "prompt": (
         "Through these relationships, fungi can help plants absorb minerals, "
         "especially 7. ___________."),
     "correct_answer": "phosphorus"},
    # Q8–10 True/False/Not Given
    {"type": "TFNG", "group_id": "pt2-passage-1",
     "prompt": "Penicillin was discovered from a type of mould.",
     "correct_answer": "True"},
    {"type": "TFNG", "group_id": "pt2-passage-1",
     "prompt": "All fungi are beneficial to agriculture.",
     "correct_answer": "False"},
    {"type": "TFNG", "group_id": "pt2-passage-1",
     "prompt": "Scientists have already identified most fungal species on Earth.",
     "correct_answer": "False"},
]

_READING_SILK_ROAD_QUESTIONS = [
    # Q11–14 Multiple Choice (4 options)
    {"type": "MCQ", "group_id": "pt2-passage-2",
     "prompt": "What does the passage say about the Silk Road?",
     "correct_answer": "C",
     "options": _MCQ_OPTS_AB(
         "It was a single road built by the Romans",
         "It was mainly used for military campaigns",
         "It was a network of routes connecting different regions",
         "It was used only to transport silk")},
    {"type": "MCQ", "group_id": "pt2-passage-2",
     "prompt": "Merchants usually",
     "correct_answer": "B",
     "options": _MCQ_OPTS_AB(
         "travelled directly from China to Europe",
         "passed goods through many market towns",
         "avoided Central Asia completely",
         "transported only religious texts")},
    {"type": "MCQ", "group_id": "pt2-passage-2",
     "prompt": "Why was silk valuable in Rome and other ancient societies?",
     "correct_answer": "B",
     "options": _MCQ_OPTS_AB(
         "It was heavy and easy to produce",
         "It was light, beautiful, and difficult to produce",
         "It was cheaper than wool",
         "It was used only by soldiers")},
    {"type": "MCQ", "group_id": "pt2-passage-2",
     "prompt": "Why did maritime trade reduce the importance of the Silk Road?",
     "correct_answer": "A",
     "options": _MCQ_OPTS_AB(
         "Ships could carry larger quantities of goods at lower cost",
         "Overland routes became illegal",
         "Silk production stopped in China",
         "Central Asian cities disappeared")},
    # Q15–17 Sentence Completion
    {"type": "SENTENCE_COMPLETION", "group_id": "pt2-passage-2",
     "prompt": "The origins of the Silk Road are often linked to China's ___________ dynasty.",
     "correct_answer": "Han"},
    {"type": "SENTENCE_COMPLETION", "group_id": "pt2-passage-2",
     "prompt": "Buddhism spread into Central Asia and China partly through ___________.",
     "correct_answer": "trade routes"},
    {"type": "SENTENCE_COMPLETION", "group_id": "pt2-passage-2",
     "prompt": "Papermaking eventually spread westward and transformed education, administration, and ___________.",
     "correct_answer": "literature"},
    # Q18–20 True/False/Not Given
    {"type": "TFNG", "group_id": "pt2-passage-2",
     "prompt": "The Silk Road carried not only goods but also ideas and religions.",
     "correct_answer": "True"},
    {"type": "TFNG", "group_id": "pt2-passage-2",
     "prompt": "Trade always increased when political order collapsed.",
     "correct_answer": "False"},
    {"type": "TFNG", "group_id": "pt2-passage-2",
     "prompt": "The Black Death may have spread partly through Eurasian trade networks.",
     "correct_answer": "True"},
]

# ---------------------------------------------------------------------------
# seed-mock2 CLI command
# ---------------------------------------------------------------------------

@click.command("seed-mock2")
@with_appcontext
def seed_mock2_command():
    """Create IELTS Academic Practice Test 2 with listening, reading, writing, and speaking."""
    from .models.exam import (
        Exam, Section, ExamType, ExamStatus, SectionType,
    )
    from .models.user import User, UserRole

    if Exam.query.filter_by(title="IELTS Academic Practice Test 2").first():
        click.echo("Practice Test 2 already exists — skipping. Delete it first to re-seed.")
        return

    teacher = User.query.filter_by(role=UserRole.TEACHER).first()
    if not teacher:
        click.echo("No teacher account found. Run 'flask seed-teacher' first.")
        return

    # ── Exam ──────────────────────────────────────────────────────────────
    exam = Exam(
        title="IELTS Academic Simulation Mini Test",
        type=ExamType.ACADEMIC,
        status=ExamStatus.PUBLISHED,
        created_by=teacher.id,
    )
    db.session.add(exam)
    db.session.flush()

    # ── Listening (30 min, 2 parts) ───────────────────────────────────────
    listening = Section(
        exam_id=exam.id,
        type=SectionType.LISTENING,
        order_index=1,
        time_limit_s=30 * 60,
        config={
            "parts": [
                {"audioFileKey": "listening/3eb09cdf-29d5-4273-8313-dafe210cc7d9/471072fb-a441-4c51-a780-3634f8eb7278/63f892b8-e838-433d-b256-f2854d22d0c6.wav",
                 "label": "Part 1 — Student Registration (Questions 1–10)",
                 "groupId": "pt2-part-1"},
                {"audioFileKey": "listening/3eb09cdf-29d5-4273-8313-dafe210cc7d9/471072fb-a441-4c51-a780-3634f8eb7278/a41704d4-976b-4718-a199-0f9fc141406c.wav",
                 "label": "Part 2 — Geopolitics Lecture (Questions 11–20)",
                 "groupId": "pt2-part-2"},
            ]
        },
    )
    db.session.add(listening)
    db.session.flush()
    _add_questions(listening.id, _LISTENING_PT2_QUESTIONS)

    # ── Reading (60 min, 2 passages) ──────────────────────────────────────
    reading = Section(
        exam_id=exam.id,
        type=SectionType.READING,
        order_index=2,
        time_limit_s=60 * 60,
        config={
            "passages": [
                {"title": "Reading Passage 1 — Science: The Hidden Intelligence of Fungi",
                 "text": _PASSAGE_FUNGI_TEXT.strip(),
                 "groupId": "pt2-passage-1"},
                {"title": "Reading Passage 2 — History: The Silk Road",
                 "text": _PASSAGE_SILK_ROAD_TEXT.strip(),
                 "groupId": "pt2-passage-2"},
            ]
        },
    )
    db.session.add(reading)
    db.session.flush()
    _add_questions(reading.id, _READING_FUNGI_QUESTIONS)
    _add_questions(reading.id, _READING_SILK_ROAD_QUESTIONS)

    # ── Writing (60 min, Task 2 only) ─────────────────────────────────────
    writing = Section(
        exam_id=exam.id,
        type=SectionType.WRITING,
        order_index=3,
        time_limit_s=60 * 60,
        config={
            "task2Prompt": (
                "<p>Some people believe that strong authoritarian leadership can create stability "
                "and economic growth, especially in times of crisis. Others argue that dictatorship "
                "limits freedom, weakens institutions, and creates long-term harm to society.</p>"
                "<p><em>To what extent do you agree or disagree with the idea that dictatorship can "
                "be beneficial for a country?</em></p>"
                "<p>Give reasons for your answer and include relevant examples from your own knowledge "
                "or experience.</p>"
                "<p>Write at least <strong>250 words</strong>.</p>"
            ),
        },
    )
    db.session.add(writing)

    # ── Speaking (14 min, 3 parts) ────────────────────────────────────────
    speaking = Section(
        exam_id=exam.id,
        type=SectionType.SPEAKING,
        order_index=4,
        time_limit_s=14 * 60,
        config={
            "parts": [
                {
                    "question": (
                        "Part 1 — Introduction & Interview\n\n"
                        "Can you introduce yourself?"
                    )
                },
                {
                    "question": (
                        "Part 2 — Long Turn\n\n"
                        "Do you prefer studying alone or with other people? Why?"
                    )
                },
                {
                    "question": (
                        "Part 3 — Discussion\n\n"
                        "What are the advantages and disadvantages of online classes, "
                        "and do you think they are effective overall?"
                    )
                },
            ]
        },
    )
    db.session.add(speaking)
    db.session.commit()

    click.echo(
        "Created: IELTS Academic Practice Test 2\n"
        f"  Listening : 20 questions across 2 parts\n"
        f"  Reading   : 20 questions across 2 passages\n"
        f"  Writing   : 1 task (Task 2 only)\n"
        f"  Speaking  : 3 parts\n"
        "Status: PUBLISHED"
    )
