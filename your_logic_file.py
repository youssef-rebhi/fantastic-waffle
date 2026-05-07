from ai import (
    generate_prompt,
    get_ai_answer,
    is_quota_or_rate_limit_error,
)
from ocr import capture_and_process_image, parse_options


def process_question_and_options(question_window, options_window, control_panel=None):
    ctx = (
        control_panel.get_ai_context()
        if control_panel is not None
        else {
            "provider_id": "gemini_flash",
            "api_key": "",
            "model": "",
            "use_prompt_enhancement": False,
        }
    )

    if not ctx.get("api_key"):
        if control_panel:
            control_panel.set_result(
                error="Add an API key in the panel (Settings) before pressing F8."
            )
        else:
            print("API key missing.")
        return

    def status(msg):
        if control_panel:
            control_panel.set_status(msg)

    question_rect = question_window.get_rect()
    options_rect = options_window.get_rect()
    status("Reading question and option areas...")
    print(f"Question area: {question_rect}")
    print(f"Options area: {options_rect}")

    question_text = capture_and_process_image(question_rect)
    options_text = capture_and_process_image(options_rect)
    options = parse_options(options_text)

    if not question_text:
        msg = "Could not read question text from the red area."
        print(msg)
        if control_panel:
            control_panel.set_result(error=msg)
        return

    if not options:
        msg = "Could not parse options from the blue area."
        print(msg)
        if control_panel:
            control_panel.set_result(error=msg)
        return

    print(f"Question: {question_text}")
    print(f"Options: {options}")

    use_enhance = bool(ctx.get("use_prompt_enhancement"))
    enhanced_prompt = None
    prompt_err = None

    if use_enhance:
        status("Enhancing prompt (extra API call)...")
        enhanced_prompt, prompt_err = generate_prompt(question_text, options, ctx)
        if prompt_err and is_quota_or_rate_limit_error(prompt_err):
            if control_panel:
                control_panel.set_result(error=prompt_err)
            print(prompt_err)
            return
        if prompt_err:
            short = (
                prompt_err
                if len(prompt_err) <= 120
                else prompt_err[:117] + "…"
            )
            status(f"Prompt step failed: {short} Trying direct answer…")
            enhanced_prompt = None

    status("Getting answer from model…")
    answer, ans_err = get_ai_answer(question_text, options, enhanced_prompt, ctx)

    if answer:
        print(f"Suggested answer: {answer}")
        if control_panel:
            control_panel.set_result(answer=str(answer))
        return

    # Prefer concrete API error message over vague fallback
    if ans_err:
        print(ans_err)
        if control_panel:
            control_panel.set_result(error=ans_err)
        return

    if prompt_err:
        print(prompt_err)
        if control_panel:
            control_panel.set_result(error=prompt_err)
        return

    msg = "No answer returned by AI."
    print(msg)
    if control_panel:
        control_panel.set_result(error=msg)
