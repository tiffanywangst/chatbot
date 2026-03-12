import requests

TERMS_URL = "https://mit-terms-v2.cloudhub.io/terms/v2/terms"

COURSES_CACHE = None


def fetch_courses():
    global COURSES_CACHE

    if COURSES_CACHE is not None:
        return COURSES_CACHE

    response = requests.get(TERMS_URL, timeout=20)
    response.raise_for_status()

    data = response.json()
    COURSES_CACHE = data.get("items", [])

    return COURSES_CACHE

def search_courses(query, courses, k=5):
    query = query.lower()
    words = query.split()

    scored = []

    for course in courses:
        text = " ".join([
            course.get("subjectId", ""),
            course.get("title", ""),
            course.get("description", ""),
            course.get("prerequisites", ""),
            course.get("instructors", "")
        ]).lower()

        score = 0

        for word in words:
            if word in text:
                score += 1

        # bonus if subject number matches exactly
        if query in course.get("subjectId", "").lower():
            score += 5

        if score > 0:
            scored.append((score, course))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [course for _, course in scored[:k]]

