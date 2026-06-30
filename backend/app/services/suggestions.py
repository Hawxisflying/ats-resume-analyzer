import re

def generate_suggestions(resume_text, jd_text, result):

    suggestions = []

    if result["skills"]["missing"]:
        suggestions.append(
            "Add relevant missing technologies only if you have practical experience."
        )

    if "github" not in resume_text.lower():
        suggestions.append(
            "Add your GitHub profile."
        )

    if "linkedin" not in resume_text.lower():
        suggestions.append(
            "Add your LinkedIn profile."
        )

    if not re.search(r"\d+%|\d+\+?", resume_text):
        suggestions.append(
            "Add measurable achievements to projects and internship."
        )

    if "portfolio" not in resume_text.lower():
        suggestions.append(
            "Add a portfolio website if available."
        )

    if len(result["projects"]["matched"]) == 0:
        suggestions.append(
            "Include projects that use technologies mentioned in the Job Description."
        )

    return suggestions