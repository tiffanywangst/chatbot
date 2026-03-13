import gradio as gr
from src.chat import Chatbot

MIT_RED = "#A31F34"
MIT_GRAY = "#8A8B8C"
MIT_COOL_GRAY = "#5A5B5C"

# Enhanced color scheme with better contrast and hierarchy
mit_theme = gr.themes.Default(
    primary_hue=gr.themes.colors.Color(
        c50="#FCEDEF", c100="#F5B8BF", c200="#ED8490", c300="#E44F5F",
        c400="#CC2A3C", c500="#A31F34", c600="#8B1A2B", c700="#6F1522",
        c800="#531019", c900="#380B11", c950="#1C0508",
    ),
    neutral_hue=gr.themes.colors.Color(
        c50="#F9FAFB", c100="#F3F4F6", c200="#E5E7EB", c300="#D1D5DB",
        c400="#9CA3AF", c500="#6B7280", c600="#4B5563", c700="#374151",
        c800="#1F2937", c900="#111827", c950="#030712",
    ),
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    radius_size=gr.themes.sizes.radius_md,
)

# Keep this to 5 or fewer to ensure they stay on one page
EXAMPLE_QUESTIONS = [
    "I'm a 6-3 junior who needs a CI-H and prefers afternoon classes.",
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
            /* Improved header banner with gradient and shadow */
            .header-banner {
                background: linear-gradient(135deg, #A31F34 0%, #8B1A2B 100%);
                padding: 24px 28px 20px;
                border-radius: 16px 16px 0 0;
                margin-bottom: 2px;
                box-shadow: 0 4px 12px rgba(163, 31, 52, 0.2);
                border-bottom: 2px solid rgba(255, 255, 255, 0.1);
            }
            .header-banner h1 {
                color: white !important;
                font-size: 26px !important;
                font-weight: 600 !important;
                margin: 0 0 6px 0;
                letter-spacing: -0.3px;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }
            .header-banner p {
                color: #FFB3BB !important;
                font-size: 14px !important;
                margin: 0;
                font-weight: 400;
                opacity: 0.95;
            }
            
            /* Enhanced chat container */
            .chat-interface {
                background: white;
                border-radius: 0 0 16px 16px;
                padding: 16px;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
            }
            
            /* Improved send button with hover effect */
            button.primary {
                background: #A31F34 !important;
                border: 1px solid #8B1A2B !important;
                transition: all 0.2s ease !important;
                font-weight: 500 !important;
                border-radius: 8px !important;
            }
            button.primary:hover {
                background: #8B1A2B !important;
                border-color: #6F1522 !important;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(163, 31, 52, 0.3);
            }
            
            /* Better textbox styling */
            .input-textbox textarea {
                border-radius: 12px !important;
                border: 2px solid #E5E7EB !important;
                transition: all 0.2s ease !important;
                font-size: 15px !important;
                padding: 12px 16px !important;
            }
            .input-textbox textarea:focus {
                border-color: #A31F34 !important;
                box-shadow: 0 0 0 3px rgba(163, 31, 52, 0.1) !important;
            }
            
            /* Enhanced example buttons */
            .examples {
                margin-top: 12px !important;
                padding: 8px !important;
                background: #F9FAFB !important;
                border-radius: 12px !important;
                border: 1px solid #E5E7EB !important;
            }
            .examples button {
                border: 1px solid #E5E7EB !important;
                background: white !important;
                color: #374151 !important;
                border-radius: 20px !important;
                padding: 8px 16px !important;
                font-size: 13px !important;
                transition: all 0.2s ease !important;
                margin: 4px !important;
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
            }
            .examples button:hover {
                border-color: #A31F34 !important;
                color: #A31F34 !important;
                background: #FCEDEF !important;
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(163, 31, 52, 0.1) !important;
            }
            
            /* Better chatbot bubble styling */
            .chatbot .message {
                border-radius: 16px !important;
                font-size: 14px !important;
                line-height: 1.5 !important;
                margin: 8px 0 !important;
            }
            .chatbot .user-message {
                background: #F3F4F6 !important;
                color: #111827 !important;
                border: 1px solid #E5E7EB !important;
            }
            .chatbot .bot-message {
                background: #FCEDEF !important;
                color: #111827 !important;
                border: 1px solid #F5B8BF !important;
                box-shadow: 0 2px 4px rgba(163, 31, 52, 0.05);
            }
            
            /* Improved avatar styling */
            .avatar-image {
                border-radius: 50% !important;
                border: 2px solid #A31F34 !important;
                padding: 2px !important;
                background: white !important;
            }
            
            /* Enhanced placeholder */
            .chatbot-placeholder {
                background: linear-gradient(145deg, #F9FAFB 0%, #F3F4F6 100%);
                border-radius: 16px !important;
                margin: 20px !important;
                border: 1px dashed #D1D5DB !important;
            }
            .chatbot-placeholder h2 {
                color: #A31F34 !important;
                font-weight: 600 !important;
            }
            
            /* Better disclaimer */
            .disclaimer {
                font-size: 12px;
                color: #6B7280;
                text-align: center;
                padding: 16px 8px 8px;
                border-top: 1px solid #E5E7EB;
                margin-top: 16px;
                background: #F9FAFB;
                border-radius: 0 0 16px 16px;
            }
            
            /* Smooth scrolling */
            .chatbot-container {
                scroll-behavior: smooth;
            }
            
            /* Hide footer */
            footer { display: none !important; }
            
            /* Loading state improvement */
            .loading {
                background: linear-gradient(90deg, #F3F4F6 25%, #E5E7EB 50%, #F3F4F6 75%);
                background-size: 200% 100%;
                animation: loading 1.5s infinite;
            }
            @keyframes loading {
                0% { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }
        """,
    ) as demo:

        with gr.Column(elem_classes="header-banner"):
            gr.HTML("""
                <h1>🎓 MIT Course Navigator</h1>
                <p>6.C395 · Algorithmic Solutions to Human Problems · Spring 2026</p>
            """)

        with gr.Column():
            gr.ChatInterface(
                chat,
                chatbot=gr.Chatbot(
                    placeholder=(
                        "<div class='chatbot-placeholder' style='text-align:center;padding:48px 24px;color:#4B5563'>"
                        "<div style='margin-bottom:16px'>"
                        "<img src='https://img.icons8.com/color/96/beaver.png' style='width:64px;height:64px;margin:0 auto;border-radius:50%;border:3px solid #A31F34;padding:4px;background:white'>"
                        "</div>"
                        "<h2 style='font-size:22px;margin-bottom:12px;color:#A31F34'>👋 Hi! I'm Tim the Beaver.</h2>"
                        "<p style='font-size:15px;margin-bottom:16px;max-width:400px;margin-left:auto;margin-right:auto'>"
                        "I can help you navigate which courses are right for you. "
                        "Try one of these examples or ask your own question!"
                        "</p>"
                        "<div style='display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-top:16px'>"
                        "<span style='background:#FCEDEF;color:#A31F34;padding:4px 12px;border-radius:20px;font-size:12px'>📚 Course 6</span>"
                        "<span style='background:#FCEDEF;color:#A31F34;padding:4px 12px;border-radius:20px;font-size:12px'>🎭 HASS</span>"
                        "<span style='background:#FCEDEF;color:#A31F34;padding:4px 12px;border-radius:20px;font-size:12px'>📝 CI-H</span>"
                        "<span style='background:#FCEDEF;color:#A31F34;padding:4px 12px;border-radius:20px;font-size:12px'>⚡ CI-M</span>"
                        "</div>"
                        "</div>"
                    ),
                    show_label=False,
                    height=450,
                    avatar_images=(
                        None, 
                        "https://img.icons8.com/color/96/beaver.png"
                    ),
                ),
                textbox=gr.Textbox(
                    placeholder="Ask about courses, requirements, scheduling conflicts...",
                    show_label=False,
                    scale=7,
                    container=False,
                ),
                examples=EXAMPLE_QUESTIONS,
                cache_examples=False,
            )

        gr.HTML('<p class="disclaimer">⚡ This chatbot uses the MIT Course Catalog as its source. Always verify with your academic advisor before making final decisions.</p>')

    return demo

if __name__ == "__main__":
    demo = create_chatbot()
    demo.launch(share=True)