from huggingface_hub import InferenceClient
from config import BASE_MODEL, MY_MODEL, HF_TOKEN
from src.catalog import fetch_courses, search_courses

SYSTEM_PROMPT = """
You are a helpful assistant that helps students explore and understand MIT’s course catalog. You have knowledge about MIT subjects, including:

- Subject numbers and titles (e.g., 6.3900, 18.600, 6.1010)

- Course descriptions and topics covered

- Prerequisites and recommended background

- Units and workload expectations

- Department or course number (e.g., Course 6, Course 18)

- Communication Intensive (CI) and HASS designations

- Undergraduate vs graduate subjects

- Relationships between introductory, intermediate, and advanced classes

When helping students:

- Ask clarifying questions about their interests, major, experience level, and goals

- Provide specific course suggestions when possible

- Explain what a course covers in simple terms

- Suggest related or follow-up courses when relevant

- Be honest when you are unsure about specific details and direct students to the official MIT catalog at catalog.mit.edu

- If the user asks questions unrelated to MIT courses, politely redirect the conversation back to MIT subjects

Key facts:

- MIT subjects are identified by subject numbers such as 6.3900 or 18.600

- The first number typically indicates the department or “course” (e.g., Course 6 for EECS, Course 18 for Mathematics)

- Many subjects have prerequisites that students should complete beforehand

- Subjects typically have unit counts representing lecture, lab, and preparation time

- The official MIT course catalog is available at catalog.mit.edu

Example questions:

- What is 6.3900 about?
- What ML classes exist at MIT?
- I want robotics courses
- What is a good intro programming class?
- Compare 6.3900 and 6.8611

Use the provided MIT catalog entries as your main source of truth.
Do not invent course descriptions, prerequisites, instructors, or offerings.
If the catalog context is incomplete, say so clearly.
"""

class Chatbot:
    def __init__(self):
        model_id = MY_MODEL if MY_MODEL else BASE_MODEL
        self.client = InferenceClient(model=model_id, token=HF_TOKEN)
        
    def format_prompt(self, user_input, history=None):
        """
        Formats the input using Llama 3.1 chat templates to ensure the 
        model stays in 'Advisor Mode'.
        """
        system_instructions = (
            "You are the MIT Course Navigator, an expert academic advisor. "
            "Your goal is to help students find courses by reasoning across multiple dimensions:"
            "Department/Major (e.g., Course 6), Prerequisites, Distribution Requirements (CI-H, HASS, REST), "
            "Class Formats, and Scheduling. "
            "\n\nStrict Rules:\n"
            "1. If a student mentions a specific requirement (like CI-H), prioritize those.\n"
            "2. Always check for prerequisite conflicts if the student mentions their year.\n"
            "3. If timing is mentioned (e.g., 'afternoon'), filter results accordingly.\n"
            "4. Be concise, professional, and encouraging."
        )
        
        # prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_instructions}<|eot_id|>"
        # prompt += f"<|start_header_id|>user<|end_header_id|>\n\n{user_input}<|eot_id|>"
        # prompt += f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        
        # return prompt
        messages =  [{"role":"system", "content":SYSTEM_PROMPT}]

        if history:
            for item in history:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    user_msg, bot_msg = item
                    messages.append({"role": "user", "content": user_msg})
                    messages.append({"role": "assistant", "content": bot_msg})
                elif isinstance(item, dict):
                    role = item.get("role")
                    content = item.get("content")
                    if role and content:
                        messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_input})
        return messages

    def get_response(self, user_input, history=None):
        """
        Generates a response using the formatted prompt.
        """
        formatted_input = self.format_prompt(user_input, history)

        try:
            response = self.client.chat_completion(
                messages=formatted_input,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"An error occurred while generating a response: {str(e)}"