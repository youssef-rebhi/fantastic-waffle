from ai import generate_prompt, get_ai_answer
from ocr import capture_and_process_image, parse_options


def process_question_and_options(question_window, options_window):
    question_rect = question_window.get_rect()
    options_rect = options_window.get_rect()
    print(f"Question area: {question_rect}")
    print(f"Options area: {options_rect}")

    question_text = capture_and_process_image(question_rect)
    options_text = capture_and_process_image(options_rect)
    options = parse_options(options_text)

    if not question_text:
        print("Could not read question text from the selected area.")
        return

    if not options:
        print("Could not parse options from the selected area.")
        return

    print(f"Question: {question_text}")
    print(f"Options: {options}")

    enhanced_prompt = generate_prompt(question_text, options)
    answer = get_ai_answer(question_text, options, enhanced_prompt)

    if answer:
        print(f"Suggested answer: {answer}")
    else:
        print("No answer returned by AI.")
