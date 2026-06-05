"""Gradio entry point for Hugging Face Spaces."""
import gradio as gr

WIP_MESSAGE = (
    "WitGym is loading — CBR-RAG comedy engine in development. "
    "Check back soon for live wit grounded in The Office precedent."
)


def respond(prompt: str) -> str:
    if not prompt.strip():
        return "Say something awkward. I'll eventually have the perfect Office-adjacent reply."
    return WIP_MESSAGE


demo = gr.Interface(
    fn=respond,
    inputs=gr.Textbox(label="Your setup", placeholder="I just got promoted and have no idea what I'm doing."),
    outputs=gr.Textbox(label="WitGym"),
    title="WitGym",
    description="Conversational wit grounded in human comedy precedent. Pipeline shipping soon.",
)

if __name__ == "__main__":
    demo.launch()
