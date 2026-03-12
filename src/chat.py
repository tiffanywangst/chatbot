from huggingface_hub import InferenceClient
from config import BASE_MODEL, MY_MODEL, HF_TOKEN
from src.catalog import fetch_courses, search_courses

SYSTEM_PROMPT = """
You are a helpful assistant that helps students explore and understand MIT’s course catalog.

You should answer using the provided MIT catalog entries as your main source of truth.
Do not invent course descriptions, prerequisites, instructors, requirements, or offerings.
If the catalog context is incomplete, ambiguous, or missing, say so clearly.

You can help with:
- subject numbers and titles
- course descriptions and topics covered
- prerequisites and recommended background
- units and workload expectations
- HASS, CI, and GIR/REST attributes
- undergraduate vs graduate level
- relationships between introductory, intermediate, and advanced classes

When helping students:
- ask clarifying questions only when necessary
- give concrete course suggestions when the context supports them
- explain why a course matches the student's interests
- suggest related follow-up subjects when useful
- stay concise, practical, and student-friendly

If the user asks about something unrelated to MIT courses, politely redirect back to MIT subjects.
"""


class Chatbot:
    def __init__(self):
        model_id = MY_MODEL if MY_MODEL else BASE_MODEL
        self.client = InferenceClient(model=model_id, token=HF_TOKEN)

        try:
            self.courses = fetch_courses()
        except Exception:
            self.courses = []

    def build_catalog_context(self, user_input, max_results=5):
        if not self.courses:
            return "No MIT catalog data was available."

        matches = search_courses(user_input, self.courses, k=max_results)

        if not matches:
            return "No directly matching MIT catalog entries were found."

        parts = []
        for course in matches:
            subject_id = course.get("subject_id", "Unknown")
            title = course.get("title", "Unknown")
            description = course.get("description", "No description provided.")
            prerequisites = course.get("prerequisites", "Unknown")
            corequisites = course.get("corequisites", "None")
            total_units = course.get("total_units", "Unknown")
            level = course.get("level", "Unknown")
            hass = course.get("hass_attribute", "None")
            ci = course.get("communication_requirement", "None")
            gir = course.get("gir_attribute", "None")
            instructors = course.get("instructors", [])
            related = course.get("related_subjects", [])
            url = course.get("url", "Unknown")
            schedule = course.get("schedule", "Unknown")

            if isinstance(instructors, list):
                instructors_text = "; ".join(instructors) if instructors else "Unknown"
            else:
                instructors_text = str(instructors)

            if isinstance(related, list):
                related_text = ", ".join(related) if related else "None"
            else:
                related_text = str(related)

            entry = (
                f"Subject: {subject_id}\n"
                f"Title: {title}\n"
                f"Level: {level}\n"
                f"Description: {description}\n"
                f"Prerequisites: {prerequisites}\n"
                f"Corequisites: {corequisites}\n"
                f"Units: {total_units}\n"
                f"HASS Attribute: {hass}\n"
                f"Communication Requirement: {ci}\n"
                f"GIR Attribute: {gir}\n"
                f"Instructors: {instructors_text}\n"
                f"Related Subjects: {related_text}\n"
                f"Schedule: {schedule}\n"
                f"Catalog URL: {url}"
            )
            parts.append(entry)

        return "\n\n---\n\n".join(parts)

    def format_prompt(self, user_input, history=None):
        catalog_context = self.build_catalog_context(user_input)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "system",
                "content": (
                    "Relevant MIT catalog entries:\n\n"
                    f"{catalog_context}\n\n"
                    "Use these entries when answering. "
                    "If the retrieved entries do not fully answer the question, say what is missing."
                ),
            },
        ]

        if history:
            for item in history:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    user_msg, bot_msg = item
                    messages.append({"role": "user", "content": str(user_msg)})
                    messages.append({"role": "assistant", "content": str(bot_msg)})
                elif isinstance(item, dict):
                    role = item.get("role")
                    content = item.get("content")
                    if role in {"user", "assistant", "system"} and content:
                        messages.append({"role": role, "content": str(content)})

        messages.append({"role": "user", "content": user_input})
        return messages

    def get_response(self, user_input, history=None):
        formatted_input = self.format_prompt(user_input, history)

        try:
            response = self.client.chat_completion(
                messages=formatted_input,
                max_tokens=400,
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"An error occurred while generating a response: {str(e)}"