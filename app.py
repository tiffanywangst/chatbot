import gradio as gr
from src.chat import Chatbot

MIT_RED = "#A31F34"

mit_theme = gr.themes.Default(
    primary_hue=gr.themes.colors.Color(
        c50="#FCEDEF", c100="#F5B8BF", c200="#ED8490", c300="#E44F5F",
        c400="#CC2A3C", c500="#A31F34", c600="#8B1A2B", c700="#6F1522",
        c800="#531019", c900="#380B11", c950="#1C0508",
    ),
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    radius_size=gr.themes.sizes.radius_md,
)

# Keep this to 5 or fewer to ensure they stay on one page
EXAMPLE_QUESTIONS = [
    "I'm a 6-3 junior who needs a CI-H and prefers afternoon classes.",
    "What REST courses work for a Course 8 major with no 8am slots?",
    "I need a HASS-S elective. I like economics and policy.",
    "What are good CI-M options for Course 6 students?",
    "I'm a freshman — what classes help me explore different majors?",
]

def create_chatbot():
    chatbot = Chatbot()

    def chat(message, history):
        try:
            return chatbot.get_response(message, history)
        except Exception as e:
            error_detail = repr(e)
            print(f"ERROR: {error_detail}")
            return f"Something went wrong: {error_detail}"

    with gr.Blocks(
        theme=mit_theme,
        title="MIT Course Navigator",
        css="""
            .header-banner {
                background: #A31F34;
                padding: 20px 24px 16px;
                border-radius: 12px 12px 0 0;
                margin-bottom: 0;
            }
            .header-banner h1 {
                color: white !important;
                font-size: 22px !important;
                font-weight: 500 !important;
                margin: 0 0 4px 0;
            }
            .header-banner p {
                color: #f0a0a8 !important;
                font-size: 13px !important;
                margin: 0;
            }
            /* Sets the Send button to MIT Red */
            button.primary {
                background: #A31F34 !important;
                border: 1px solid #8B1A2B !important;
            }
            .disclaimer {
                font-size: 12px;
                color: #888;
                text-align: center;
                padding: 8px;
            }
            footer { display: none !important; }
        """,
    ) as demo:

        with gr.Column(elem_classes="header-banner"):
            gr.HTML("""
                <h1>MIT Course Navigator</h1>
                <p>6.C395 · Algorithmic Solutions to Human Problems · Spring 2026</p>
            """)

        gr.ChatInterface(
            chat,
            chatbot=gr.Chatbot(
                placeholder=(
                    "<div style='text-align:center;padding:40px 20px;color:#444'>"
                    "<h2 style='font-size:20px;margin-bottom:8px'>👋 Hi! I'm Tim the Beaver.</h2>"
                    "<p>I can help you navigate the MIT Course Catalog. <br>"
                    "Select an example below or type your own question to start!</p>"
                    "</div>"
                ),
                show_label=False,
                height=450,
                # Using a Beaver icon for the respondent
                avatar_images=(
                    None, 
                    "https://img.icons8.com/color/96/beaver.png"
                ),
            ),
            textbox=gr.Textbox(
                placeholder="Ask about courses, CI-H requirements, scheduling conflicts...",
                show_label=False,
                scale=7,
            ),
            examples=EXAMPLE_QUESTIONS,
            cache_examples=False,
        )

        gr.HTML('<p class="disclaimer">This chatbot uses the MIT Course Catalog as the source. Always verify with your advisor.</p>')

    return demo

if __name__ == "__main__":
    demo = create_chatbot()
    demo.launch(share=True)
