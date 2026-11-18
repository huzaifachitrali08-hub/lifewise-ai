"""LIFEWISE goal planning: goal-aware roadmaps plus fully manual plans."""
from datetime import date, timedelta
import re


def _date(value):
    if isinstance(value, str):
        return date.fromisoformat(value)
    return value


def detect_goal_type(title, area=""):
    text = f"{title or ''} {area or ''}".lower()
    if re.search(r"\b(doctor|physician|mbbs|medical school|surgeon)\b", text):
        return "medical_career"
    if re.search(r"\b(data scientist|data science)\b", text):
        return "data_science"
    if re.search(r"\b(software engineer|software developer|programmer)\b", text):
        return "software_career"
    if re.search(r"\b(business|startup|company|entrepreneur)\b", text):
        return "business"
    if re.search(r"\b(learn|learning|master|skill|python|english)\b", text):
        return "skill_learning"
    return "general"


def _medical_phases(country, education, starting_point):
    place = (country or "your country").strip()
    edu = (education or "your current education level").strip()
    return [
        ("1 · Check eligibility and starting point", [
            ("Confirm the medical pathway", f"Check the official medical regulator and university requirements in {place}. Confirm the recognized degree, entry route, age/subject rules and current admission cycle."),
            ("Map your education gaps", f"Starting point: {edu}. Compare your completed qualifications and science subjects with the official entry requirements. List every missing prerequisite."),
            ("Build an admission budget and shortlist", "Estimate tuition, application, examination, travel and living costs. Shortlist recognized institutions and check scholarships and deadlines."),
        ]),
        ("2 · Meet academic and entrance requirements", [
            ("Complete required school or college qualifications", "Follow the required science/pre-medical subjects and minimum grades for your chosen pathway. Do not assume eligibility until verified."),
            ("Prepare for the medical entrance test", "Use the current official syllabus, diagnostic tests and a weekly study timetable. Practise timed questions and review weak topics."),
            ("Apply to eligible medical institutions", "Prepare documents, submit applications before official deadlines and track test results, merit lists and admission decisions."),
        ]),
        ("3 · Complete the medical degree", [
            ("Begin the recognized medical degree", "After admission, follow the institution's approved curriculum and academic calendar. Confirm the expected degree duration directly with the institution."),
            ("Progress through academic and clinical training", "Complete required modules, examinations, laboratory work and supervised clinical rotations. Seek support early when a subject is difficult."),
            ("Meet graduation requirements", "Pass all required assessments and clinical competencies, complete required placements and obtain the recognized degree."),
        ]),
        ("4 · Complete supervised practice and registration", [
            ("Verify internship or house-job requirements", f"Check the current licensing rules in {place}; required supervised practice and its duration vary by jurisdiction."),
            ("Complete required supervised clinical practice", "Apply to an approved training site, complete required rotations and maintain the evidence and evaluations required by the regulator."),
            ("Apply for professional registration or licence", "Submit the degree, training evidence, identity documents and any required examinations to the relevant regulator. Confirm registration before practising."),
        ]),
        ("5 · Establish the next professional milestone", [
            ("Choose a first clinical direction", "Explore supervised entry-level roles and specialties with qualified mentors. Understand that specialist training is a separate pathway."),
            ("Prepare applications and interviews", "Build a factual CV, gather references and prepare for the selection process applicable in your country."),
            ("Review your first-year development plan", "Set learning, supervision and professional development goals for your first year of practice."),
        ]),
    ]


def _generic_phases(kind):
    if kind == "data_science":
        return [
            ("1 · Define the target role", [("Choose a data science direction", "Compare analyst, data scientist and machine-learning roles; identify the target role and local entry requirements."), ("Assess your starting skills", "Review mathematics, statistics, Python, SQL and communication skills; record strengths and gaps."), ("Create a learning schedule", "Choose learning resources and allocate realistic weekly study time.")]),
            ("2 · Build core foundations", [("Learn Python and data handling", "Practise Python fundamentals, pandas and data cleaning with small datasets."), ("Learn statistics and SQL", "Study descriptive statistics, probability, hypothesis testing and practical SQL queries."), ("Practise data visualization", "Create clear charts and explain the insight each chart communicates.")]),
            ("3 · Build evidence of ability", [("Complete an end-to-end project", "Choose a real question, obtain a suitable dataset, clean it, analyse it and document findings."), ("Publish a portfolio", "Write project READMEs, explain decisions and share reproducible work."), ("Get feedback and improve", "Ask a teacher or practitioner to review the project and address the most important gaps.")]),
            ("4 · Prepare for opportunities", [("Practise technical interviews", "Review SQL, Python, statistics and project explanations using realistic questions."), ("Prepare applications", "Create a truthful CV and tailor applications to entry-level roles or internships."), ("Review progress and next skills", "Measure readiness against real job descriptions and plan the next learning cycle.")]),
        ]
    if kind == "software_career":
        return [("1 · Define your target", [("Choose a development path", "Select a target such as web, mobile, backend or embedded development."), ("Assess your foundations", "Review programming, problem solving, Git and computer science basics."), ("Set a sustainable schedule", "Choose a learning path and weekly time budget.")]), ("2 · Build foundations", [("Learn a programming language", "Study syntax, data structures, debugging and testing."), ("Learn developer tools", "Practise Git, command line, editor and basic deployment."), ("Build small exercises", "Complete increasingly challenging exercises and review mistakes.")]), ("3 · Build portfolio projects", [("Create a complete project", "Build something useful with clear requirements and working functionality."), ("Test and document your work", "Add tests, a README and setup instructions."), ("Get code review", "Ask an experienced developer or teacher for feedback and improve the project.")]), ("4 · Prepare for work", [("Practise interviews", "Review problem solving and explain your own projects."), ("Prepare a portfolio and CV", "Present real skills and links to working projects."), ("Apply and iterate", "Apply to suitable roles and use feedback to improve.")])]
    if kind == "business":
        return [("1 · Validate the idea", [("Define the customer problem", "Describe who has the problem and what evidence shows it matters."), ("Interview potential customers", "Speak with potential customers and record patterns without leading their answers."), ("Check feasibility", "Estimate costs, regulations, competitors and operational constraints.")]), ("2 · Test a small offer", [("Design a minimum viable offer", "Create the smallest safe and useful version of the product or service."), ("Set a simple budget", "Estimate startup costs, pricing, cash flow and a loss limit."), ("Run a small pilot", "Test with a limited group and collect honest feedback.")]), ("3 · Improve operations", [("Improve the offer", "Use customer evidence to fix the most important problem."), ("Create repeatable processes", "Document delivery, support, quality and record keeping."), ("Review legal and tax obligations", "Verify local registration, licensing, tax and consumer requirements with official sources.")]), ("4 · Decide whether to grow", [("Measure business results", "Review demand, costs, customer satisfaction and cash runway."), ("Choose a growth experiment", "Test one affordable channel or improvement at a time."), ("Make a continue or change decision", "Use evidence to decide whether to grow, adjust or stop.")])]
    if kind == "skill_learning":
        return [("1 · Set a clear learning outcome", [("Define what you will be able to do", "Describe a visible task or skill that proves progress."), ("Check your current level", "Try a short baseline exercise and identify gaps."), ("Choose learning resources", "Select a structured course, book or practice resource.")]), ("2 · Learn the fundamentals", [("Study one core concept", "Learn a small topic and write a plain-language explanation."), ("Practise deliberately", "Complete exercises that target the concept."), ("Review mistakes", "Record errors and repeat practice until performance improves.")]), ("3 · Apply the skill", [("Complete a practical task", "Use the skill to create a real output."), ("Get feedback", "Ask a knowledgeable person to review your result."), ("Improve your work", "Apply feedback and save the improved version.")]), ("4 · Demonstrate and maintain", [("Complete a final assessment", "Test yourself against the original success criteria."), ("Collect evidence", "Save a project, recording, certificate or other proof where appropriate."), ("Create a maintenance routine", "Plan how to keep practising and extend the skill.")])]
    return [("1 · Clarify the goal", [("Define success", "Write a measurable description of the result you want."), ("Assess your starting point", "List your current abilities, resources and constraints."), ("Identify requirements", "Research the important steps, dependencies and risks for this goal.")]), ("2 · Build foundations", [("Learn the first essential requirement", "Choose the most important missing skill or resource and work on it."), ("Practise with a small task", "Apply what you learned and record the result."), ("Review and fix a gap", "Identify one weakness and take a specific improvement step.")]), ("3 · Do meaningful work", [("Complete a milestone project", "Create a real output that demonstrates progress."), ("Get informed feedback", "Ask a suitable teacher, mentor or experienced person to review it."), ("Improve the result", "Use feedback to make a measurable improvement.")]), ("4 · Evaluate and continue", [("Measure progress", "Compare evidence with your success criteria."), ("Close the biggest gap", "Complete the most important unfinished requirement."), ("Set the next milestone", "Record what worked and choose the next realistic step.")])]


def build_smart_action_plan(title, area, target_date=None, weekly_hours=5,
                            starting_point="Beginner", success_measure="",
                            country="", education="", current_situation=""):
    """Build goal-specific milestones. Dates are distributed across the requested horizon."""
    if not title or not title.strip():
        raise ValueError("Enter a goal before creating a plan.")
    kind = detect_goal_type(title, area)
    today = date.today()
    years = 7 if kind == "medical_career" else 2 if kind in ("data_science", "software_career", "business") else 1
    if target_date:
        end = _date(target_date)
        if end < today:
            raise ValueError("The target date must be today or in the future.")
    else:
        end = today + timedelta(days=round(years * 365.25))
    if kind == "medical_career":
        phases = _medical_phases(country, education, starting_point)
    else:
        phases = _generic_phases(kind)
    total_days = max(1, (end - today).days)
    actions = []
    phase_count = len(phases)
    weights = ([0.12, 0.12, 0.58, 0.13, 0.05] if kind == "medical_career"
               else [1 / phase_count] * phase_count)
    elapsed_weight = 0.0
    for pidx, (phase, tasks) in enumerate(phases):
        phase_weight = weights[pidx]
        for tidx, (task, desc) in enumerate(tasks):
            fraction = elapsed_weight + phase_weight * ((tidx + 1) / len(tasks))
            due = today + timedelta(days=round(total_days * fraction))
            actions.append({"phase": phase, "title": task, "description": desc,
                            "due_date": min(due, end).isoformat()})
        elapsed_weight += phase_weight
    return {"goal_type": kind, "target_date": end, "actions": actions,
            "estimated_years": years, "planning_note": "Timeline is an estimate. Verify formal entry, licensing, legal and professional requirements with the relevant official body; revise dates when your circumstances are known."}


def build_action_plan(title, area, target_date, weekly_hours=5,
                      starting_point="Beginner", success_measure=""):
    """Backward-compatible alias for the goal-aware planner."""
    return build_smart_action_plan(title, area, target_date, weekly_hours,
                                   starting_point, success_measure)["actions"]


def calculate_progress(actions):
    total = len(actions)
    completed = sum(1 for action in actions if action.get("status") == "Completed")
    in_progress = sum(1 for action in actions if action.get("status") == "In Progress")
    return {"total": total, "completed": completed, "in_progress": in_progress,
            "pending": total - completed - in_progress,
            "percent": round((completed / total) * 100) if total else 0}
