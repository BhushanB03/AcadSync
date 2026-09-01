"""
Grade service: business logic for grade calculation, template application, and target grade analysis.
"""

from app.extensions import db
from app.models.assessment import SubjectComponent, SubjectGradeBoundary
from app.models.grade_template import GradeTemplate
from app.services.formula_engine import evaluate_formula
from typing import Dict, Optional, Tuple


def get_component_values(subject_components: list, calculation_mode: str = 'raw') -> Dict[str, float]:
    """
    Returns the values to use when evaluating a formula.

    In raw mode, component values are the actual obtained marks as entered by the user.
    In percentage mode, each component is normalized to a 0-100 scale before evaluation.

    Args:
        subject_components: List of SubjectComponent objects for a subject
        calculation_mode: 'raw' or 'percentage'

    Returns:
        Dict mapping component_code to numeric values for formula evaluation.
        Only includes components where obtained_marks is not None.
    """
    normalized_mode = (calculation_mode or 'raw').lower()
    if normalized_mode not in {'raw', 'percentage'}:
        normalized_mode = 'raw'

    component_values = {}
    for component in subject_components:
        if component.obtained_marks is None:
            continue

        if normalized_mode == 'raw':
            component_values[component.component_code] = float(component.obtained_marks)
        else:
            component_values[component.component_code] = component.get_percentage()

    return component_values


def get_percentage_values(subject_components: list, calculation_mode: str = 'raw') -> Dict[str, float]:
    """Backward-compatible wrapper for formula evaluation value extraction."""
    return get_component_values(subject_components, calculation_mode=calculation_mode)


def calculate_final_score(subject) -> Tuple[Optional[float], Optional[str]]:
    """
    Calculates the final score for a subject using its formula and component marks.
    
    Args:
        subject: Subject instance with components, grade_boundaries, and formula_text
    
    Returns:
        Tuple of (score: float or None, message: str or None)
        - If all required marks are entered: (final_score, None)
        - If some required marks are missing: (None, "Cannot calculate yet: missing marks for X, Y, Z")
        - If formula is not set: (None, "No formula configured for this subject")
        - If formula evaluation fails: (None, "Formula error: ...")
    
    Examples:
        With all marks:
        >>> calculate_final_score(subject)
        (88.45, None)
        
        With missing marks:
        >>> calculate_final_score(subject)
        (None, "Cannot calculate yet: missing marks for Qz1, Qz2")
        
        Without formula:
        >>> calculate_final_score(subject)
        (None, "No formula configured for this subject")
    """
    # Check if formula is configured
    if not subject.formula_text:
        return None, "No formula configured for this subject"

    calculation_mode = (getattr(subject, 'calculation_mode', 'raw') or 'raw').lower()
    component_values = get_component_values(subject.components, calculation_mode)

    # Try to evaluate the formula
    try:
        score = evaluate_formula(subject.formula_text, component_values)
        return score, None
    except ValueError as e:
        error_msg = str(e)

        # Check if error is due to missing marks (variables in formula but not in component_values)
        if "Missing variable value:" in error_msg:
            missing_vars = []
            for component in subject.components:
                if component.component_code not in component_values:
                    missing_vars.append(component.component_code)

            if missing_vars:
                missing_str = ", ".join(sorted(missing_vars))
                return None, f"Cannot calculate yet: missing marks for {missing_str}"

        # Generic formula error
        return None, f"Formula error: {error_msg}"


def get_grade_for_score(score: float, grade_boundaries: list) -> str:
    """
    Determines the grade label for a numeric score.
    
    Args:
        score: The computed final score (e.g., 88.5)
        grade_boundaries: List of SubjectGradeBoundary objects, sorted by score ranges
    
    Returns:
        Grade label (e.g., "S", "A", "B") if score falls within a boundary, else "N/A"
    
    Notes:
        - Grade boundaries should not overlap for reliable results
        - Checks if min_score <= score <= max_score (inclusive on both ends)
    
    Examples:
        >>> grade_boundaries = [
        ...     SubjectGradeBoundary(grade_label="S", min_score=90, max_score=100),
        ...     SubjectGradeBoundary(grade_label="A", min_score=80, max_score=89.99),
        ... ]
        >>> get_grade_for_score(88.5, grade_boundaries)
        "A"
    """
    for boundary in grade_boundaries:
        if boundary.min_score <= score <= boundary.max_score:
            return boundary.grade_label
    
    return "N/A"


def calculate_target_grade(subject, target_grade_label: str) -> Tuple[bool, Optional[float], str]:
    """
    Calculates the required score in missing components to achieve a target grade.
    
    SIMPLIFIED APPROACH (Uniform Distribution):
    Assumes all missing components need the SAME percentage score.
    For a first working version, this solves for one variable X representing
    "the percentage needed uniformly in each remaining missing component".
    
    Args:
        subject: Subject instance with components, grade_boundaries, and formula_text
        target_grade_label: The target grade (e.g., "S", "A", "B")
    
    Returns:
        Tuple of (achievable: bool, required_percentage: float or None, message: str)
        - If achievable with X <= 100: (True, X, "Uniform score of X% required in missing components")
        - If not achievable even with 100%: (False, None, "Cannot achieve grade S even with 100%")
        - If all marks already entered: (True, None, "All marks already entered")
        - If no formula: (False, None, "No formula configured")
    
    Examples:
        >>> calculate_target_grade(subject, "S")
        (True, 92.5, "Uniform score of 92.5% required in missing components")
        
        >>> calculate_target_grade(subject, "S")
        (False, None, "Cannot achieve grade S even with 100%")
    
    Notes:
        - This is a simplified uniform-distribution approach
        - Could be enhanced later to solve for individual missing components
        - Uses binary search on [0, 100] to find the minimum uniform percentage needed
    """
    
    # Check if formula exists
    if not subject.formula_text:
        return False, None, "No formula configured for this subject"
    
    # Find the target grade boundary
    target_boundary = None
    for boundary in subject.grade_boundaries:
        if boundary.grade_label == target_grade_label:
            target_boundary = boundary
            break
    
    if not target_boundary:
        return False, None, f"Grade {target_grade_label} not found in boundaries"
    
    calculation_mode = (getattr(subject, 'calculation_mode', 'raw') or 'raw').lower()
    component_values = get_component_values(subject.components, calculation_mode)
    missing_components = [c for c in subject.components if c.component_code not in component_values]

    # If all marks are entered
    if not missing_components:
        return True, None, "All marks already entered"

    missing_codes = [c.component_code for c in missing_components]

    def test_value(uniform_value: float) -> float:
        """Returns the final score when all missing components are set to the same value."""
        test_values = component_values.copy()
        for component in missing_components:
            if calculation_mode == 'raw':
                max_marks = float(component.max_marks) if component.max_marks is not None else 100.0
                test_values[component.component_code] = min(float(uniform_value), max_marks)
            else:
                test_values[component.component_code] = float(uniform_value)

        try:
            return evaluate_formula(subject.formula_text, test_values)
        except ValueError:
            return -999.0

    if calculation_mode == 'raw':
        max_possible = min(
            (float(component.max_marks) if component.max_marks is not None else 100.0)
            for component in missing_components
        )
        max_score = test_value(max_possible)
        if max_score < target_boundary.min_score:
            return False, None, f"Cannot achieve grade {target_grade_label} even with the maximum marks in all missing components"

        low, high = 0.0, max_possible
        required_value = None

        for _ in range(50):
            mid = (low + high) / 2.0
            score = test_value(mid)

            if score >= target_boundary.min_score:
                required_value = mid
                high = mid
            else:
                low = mid

        if required_value is None:
            required_value = max_possible

        required_value = round(required_value, 2)
        message = f"Uniform score of {required_value} marks required in missing components: {', '.join(missing_codes)}"
        return True, required_value, message

    # Percentage mode uses a 0-100 scale, which is the historical behaviour of the app.
    max_score = test_value(100.0)
    if max_score < target_boundary.min_score:
        return False, None, f"Cannot achieve grade {target_grade_label} even with 100% in all missing components"

    low, high = 0.0, 100.0
    required_pct = None

    for _ in range(50):
        mid = (low + high) / 2.0
        score = test_value(mid)

        if score >= target_boundary.min_score:
            required_pct = mid
            high = mid
        else:
            low = mid

    if required_pct is None:
        required_pct = 100.0

    required_pct = round(required_pct, 2)
    message = f"Uniform score of {required_pct}% required in missing components: {', '.join(missing_codes)}"
    return True, required_pct, message


def apply_template_to_subject(template: GradeTemplate, subject) -> str:
    """
    Applies a GradeTemplate to a Subject.
    Copies components, grade boundaries, and formula from template to subject.
    
    Args:
        template: GradeTemplate instance
        subject: Subject instance to apply template to
    
    Returns:
        Success message string
    
    Side Effects:
        - Clears any existing subject.components and subject.grade_boundaries
        - Creates new SubjectComponent rows (obtained_marks = None initially)
        - Creates new SubjectGradeBoundary rows
        - Sets subject.formula_text to template.formula_text
        - Commits to database
    
    Raises:
        ValueError: If template does not have components or formula
    """
    
    # Validate template has required data
    if not template.components:
        raise ValueError(f"Template '{template.name}' has no components")
    if not template.formula_text:
        raise ValueError(f"Template '{template.name}' has no formula")
    
    # Clear existing components and boundaries
    subject.components.clear()
    subject.grade_boundaries.clear()
    
    # Copy components from template
    for template_component in template.components:
        new_component = SubjectComponent(
            subject_id=subject.id,
            component_code=template_component.component_code,
            component_name=template_component.component_name,
            max_marks=template_component.max_marks,
            obtained_marks=None  # Marks to be entered later
        )
        db.session.add(new_component)
    
    # Copy grade boundaries from template
    for template_boundary in template.grade_boundaries:
        new_boundary = SubjectGradeBoundary(
            subject_id=subject.id,
            grade_label=template_boundary.grade_label,
            min_score=template_boundary.min_score,
            max_score=template_boundary.max_score
        )
        db.session.add(new_boundary)
    
    # Copy formula and calculation mode to subject
    subject.formula_text = template.formula_text
    subject.calculation_mode = template.calculation_mode

    # Commit to database
    db.session.commit()

    return f"Template '{template.name}' applied successfully to '{subject.name}'"
