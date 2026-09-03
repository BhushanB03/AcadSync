"""
Context builder service for AcadSync AI Academic Assistant.
Aggregates a factual, comprehensive snapshot of the user's academic status
across both VIT and IITM universities, pre-calculating all scores in Python
before sending context to the Gemini LLM.
"""

from datetime import date
from app.models.subject import Subject
from app.models.task import Task
from app.services.grade_service import calculate_final_score, get_grade_for_score


def build_user_context(user) -> str:
    """
    Gathers a comprehensive text summary of the user's academic state.

    Includes:
    - Active subjects (name, code, university, term, subject type)
    - Pre-calculated grades/scores via grade_service (or missing marks status)
    - Overdue tasks (count and list with details)
    - Upcoming tasks (next 10 non-completed, sorted by due date)
    - IITM weekly progress completion status

    Returns:
        str: Clean, readable plain text snapshot for injection into the AI prompt.
    """
    today = date.today()
    lines = []
    lines.append(f"ACADEMIC SNAPSHOT FOR: {user.name} (ID: {user.id})")
    lines.append(f"Generated on: {today.strftime('%A, %B %d, %Y')}")
    lines.append("")

    # 1. Subjects & Grades
    lines.append("=== 1. ACTIVE SUBJECTS & PRE-CALCULATED GRADES ===")
    subjects = Subject.query.filter_by(user_id=user.id, status='Active').order_by(Subject.university.asc(), Subject.name.asc()).all()

    if not subjects:
        # Fallback to all subjects if none marked 'Active'
        subjects = Subject.query.filter_by(user_id=user.id).order_by(Subject.university.asc(), Subject.name.asc()).all()

    if not subjects:
        lines.append("No registered subjects found.")
    else:
        for sub in subjects:
            grade_summary = ""
            if sub.formula_text:
                score, message = calculate_final_score(sub)
                if score is not None:
                    grade = get_grade_for_score(score, sub.grade_boundaries)
                    grade_summary = f"Pre-calculated Score: {score:.2f}/100 | Current Grade: {grade}"
                else:
                    grade_summary = f"Score not yet calculable ({message})"
            else:
                grade_summary = "No grading formula configured yet"

            lines.append(
                f"- [{sub.university}] {sub.name} ({sub.code}) - {sub.subject_type}, Term: {sub.term}\n"
                f"  Status: {grade_summary}"
            )
    lines.append("")

    # 2. Overdue Tasks
    lines.append("=== 2. OVERDUE TASKS ===")
    all_pending_tasks = Task.query.filter(
        Task.user_id == user.id,
        Task.status != 'Completed'
    ).all()

    overdue_tasks = [
        t for t in all_pending_tasks
        if t.due_date and t.due_date < today
    ]
    # Sort overdue by oldest due date first
    overdue_tasks.sort(key=lambda t: t.due_date)

    if overdue_tasks:
        lines.append(f"Total Overdue Tasks: {len(overdue_tasks)}")
        for t in overdue_tasks:
            sub_label = f"{t.subject.name} ({t.subject.code})" if t.subject else "Standalone"
            due_str = t.due_date.strftime('%Y-%m-%d')
            days_overdue = (today - t.due_date).days
            lines.append(
                f"- [OVERDUE by {days_overdue} days] \"{t.title}\" | Due: {due_str} | Priority: {t.priority} | Subject: {sub_label}"
            )
    else:
        lines.append("No overdue tasks! All assignments and to-dos are on track.")
    lines.append("")

    # 3. Upcoming Tasks (Next 10 non-completed)
    lines.append("=== 3. UPCOMING TASKS (NEXT 10) ===")
    # Sort pending tasks: those with due dates first (closest first), then tasks without due dates
    sorted_upcoming = sorted(
        all_pending_tasks,
        key=lambda t: (t.due_date is None, t.due_date if t.due_date else date.max, t.priority != 'High')
    )[:10]

    if sorted_upcoming:
        for t in sorted_upcoming:
            sub_label = f"{t.subject.name} ({t.subject.code})" if t.subject else "Standalone"
            due_str = t.due_date.strftime('%Y-%m-%d') if t.due_date else "No due date"
            lines.append(
                f"- \"{t.title}\" | Due: {due_str} | Priority: {t.priority} | Status: {t.status} | Subject: {sub_label}"
            )
    else:
        lines.append("No pending upcoming tasks.")
    lines.append("")

    # 4. IITM Weekly Progress Summary
    lines.append("=== 4. IITM WEEKLY PROGRESS SUMMARY ===")
    iitm_subjects = [s for s in subjects if s.university == 'IITM']
    if not iitm_subjects:
        # Check all user subjects in case none were in the active list
        iitm_subjects = Subject.query.filter_by(user_id=user.id, university='IITM').all()

    if iitm_subjects:
        for s in iitm_subjects:
            weeks = s.weekly_progress
            total_weeks = len(weeks)
            if total_weeks > 0:
                completed = sum(1 for w in weeks if w.status == 'Completed')
                in_progress = sum(1 for w in weeks if w.status == 'In Progress')
                pct = (completed / total_weeks) * 100
                lines.append(
                    f"- {s.name} ({s.code}): {completed}/{total_weeks} weeks completed ({pct:.0f}%) | {in_progress} in progress"
                )
            else:
                lines.append(f"- {s.name} ({s.code}): No weekly tracking modules created yet.")
    else:
        lines.append("No IITM subjects registered.")

    return "\n".join(lines)
