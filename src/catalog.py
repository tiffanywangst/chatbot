import re
import requests
from urllib.parse import quote

ALL_COURSES_URL = "https://fireroad.mit.edu/api/courses/all?full=true"
LOOKUP_URL = "https://fireroad.mit.edu/api/courses/lookup"
SEARCH_URL = "https://fireroad.mit.edu/api/courses/search"
DEPT_URL = "https://fireroad.mit.edu/api/courses/dept"

COURSES_CACHE = None


def fetch_courses():
    global COURSES_CACHE

    if COURSES_CACHE is not None:
        return COURSES_CACHE

    response = requests.get(ALL_COURSES_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    COURSES_CACHE = data if isinstance(data, list) else []
    return COURSES_CACHE


def _normalize(text):
    if text is None:
        return ""
    return str(text).strip().lower()


def _looks_like_subject_id(query):
    q = query.strip().upper()
    return bool(re.fullmatch(r"[A-Z0-9]+(?:\.[A-Z0-9]+)+", q))


def _extract_subject_ids(text):
    if not text:
        return []
    matches = re.findall(r"\b[A-Z0-9]+(?:\.[A-Z0-9]+)+\b", text.upper())
    # preserve order, remove duplicates
    seen = set()
    out = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _extract_dept_code(text):
    if not text:
        return None

    text = text.strip()

    patterns = [
        r"\bcourse\s+([A-Za-z0-9]+)\b",
        r"\bdept(?:artment)?\s+([A-Za-z0-9]+)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).upper()

    # If the query starts with something like "21W" or "WGS"
    m = re.match(r"^\s*([A-Za-z]+[A-Za-z0-9]*|\d+[A-Za-z]*)\b", text)
    if m:
        token = m.group(1).upper()
        if token not in {"WHAT", "SHOW", "FIND", "LIST", "COMPARE", "I", "IM"}:
            return token

    return None


def _parse_filters(query):
    q = query.lower()

    filters = {
        "gir": "off",
        "hass": "off",
        "ci": "off",
        "offered": "off",
        "level": "off",
    }

    # HASS
    if "hass-a" in q:
        filters["hass"] = "a"
    elif "hass-s" in q:
        filters["hass"] = "s"
    elif "hass-h" in q:
        filters["hass"] = "h"
    elif "hass" in q:
        filters["hass"] = "any"

    # CI
    if "ci-hw" in q:
        filters["ci"] = "cihw"
    elif "ci-h" in q:
        filters["ci"] = "cih"
    elif "not ci" in q or "non-ci" in q:
        filters["ci"] = "not-ci"

    # GIR / REST / LAB
    if "rest" in q:
        filters["gir"] = "rest"
    elif "lab" in q:
        filters["gir"] = "lab"
    elif "gir" in q:
        filters["gir"] = "any"

    # Semester offered
    if "fall" in q:
        filters["offered"] = "fall"
    elif "spring" in q:
        filters["offered"] = "spring"
    elif "iap" in q:
        filters["offered"] = "IAP"
    elif "summer" in q:
        filters["offered"] = "summer"

    # Level
    if "undergrad" in q or "undergraduate" in q:
        filters["level"] = "undergrad"
    elif "grad" in q or "graduate" in q:
        filters["level"] = "grad"

    return filters


def _lookup_subject(subject_id):
    url = f"{LOOKUP_URL}/{quote(subject_id)}"
    response = requests.get(url, params={"full": "true"}, timeout=20)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


def _search_endpoint(term, filters=None):
    filters = filters or {}
    url = f"{SEARCH_URL}/{quote(term)}"
    params = {"full": "true", "type": "contains"}
    params.update(filters)

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def _dept_endpoint(dept_code):
    url = f"{DEPT_URL}/{quote(dept_code)}"
    response = requests.get(url, params={"full": "true"}, timeout=20)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def _local_rank(query, courses):
    query_norm = _normalize(query)
    words = [w for w in re.split(r"\s+", query_norm) if w]

    scored = []
    for course in courses:
        subject_id = _normalize(course.get("subject_id", ""))
        old_id = _normalize(course.get("old_id", ""))
        title = _normalize(course.get("title", ""))
        description = _normalize(course.get("description", ""))
        prerequisites = _normalize(course.get("prerequisites", ""))
        corequisites = _normalize(course.get("corequisites", ""))
        hass = _normalize(course.get("hass_attribute", ""))
        ci = _normalize(course.get("communication_requirement", ""))
        gir = _normalize(course.get("gir_attribute", ""))
        level = _normalize(course.get("level", ""))

        joint = " ".join(course.get("joint_subjects", []) or []).lower()
        equiv = " ".join(course.get("equivalent_subjects", []) or []).lower()
        meets = " ".join(course.get("meets_with_subjects", []) or []).lower()
        related = " ".join(course.get("related_subjects", []) or []).lower()
        instructors = " ".join(course.get("instructors", []) or []).lower()

        haystack = " ".join([
            subject_id, old_id, title, description, prerequisites, corequisites,
            hass, ci, gir, level, joint, equiv, meets, related, instructors
        ])

        score = 0

        if query_norm == subject_id:
            score += 100
        if query_norm == old_id and old_id:
            score += 90
        if query_norm in subject_id and query_norm:
            score += 40
        if query_norm in old_id and query_norm and old_id:
            score += 35
        if query_norm == title:
            score += 30
        if query_norm in title and query_norm:
            score += 20

        for word in words:
            if word in subject_id:
                score += 15
            if word in old_id and old_id:
                score += 12
            if word in title:
                score += 8
            if word in hass or word in ci or word in gir:
                score += 6
            if word in haystack:
                score += 2

        if score > 0:
            scored.append((score, course))

    scored.sort(key=lambda x: x[0], reverse=True)

    seen = set()
    results = []
    for _, course in scored:
        sid = course.get("subject_id")
        if sid not in seen:
            seen.add(sid)
            results.append(course)
    return results


def search_courses(query, courses=None, k=5):
    """
    Hybrid retrieval strategy:
    1. Exact lookup for explicit subject IDs
    2. FireRoad search endpoint with filters for HASS/CI/GIR queries
    3. Department endpoint for Course X queries
    4. Local reranking over all cached courses as fallback
    """
    courses = courses if courses is not None else fetch_courses()
    results = []

    # 1) exact subject-id lookup(s)
    subject_ids = _extract_subject_ids(query)
    for subject_id in subject_ids:
        course = _lookup_subject(subject_id)
        if course:
            results.append(course)

    if results:
        return results[:k]

    # 2) filtered search endpoint
    filters = _parse_filters(query)
    search_term = query.strip()

    # remove some structural words to make search term cleaner
    search_term = re.sub(
        r"\b(hass-a|hass-s|hass-h|hass|ci-hw|ci-h|rest|gir|lab|fall|spring|iap|summer|undergrad|undergraduate|grad|graduate)\b",
        "",
        search_term,
        flags=re.IGNORECASE,
    )
    search_term = re.sub(r"\s+", " ", search_term).strip()

    if search_term:
        try:
            endpoint_results = _search_endpoint(search_term, filters=filters)
            if endpoint_results:
                ranked = _local_rank(query, endpoint_results)
                if ranked:
                    return ranked[:k]
        except requests.RequestException:
            pass

    # 3) department endpoint for "Course 6", "Course 21W", etc.
    dept_code = _extract_dept_code(query)
    if dept_code:
        try:
            dept_results = _dept_endpoint(dept_code)
            if dept_results:
                ranked = _local_rank(query, dept_results)
                if ranked:
                    return ranked[:k]
        except requests.RequestException:
            pass

    # 4) fallback local rank over all courses
    ranked = _local_rank(query, courses)
    return ranked[:k]