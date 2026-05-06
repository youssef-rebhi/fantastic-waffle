from ui import setup_ui, setup_hotkeys
from your_logic_file import process_question_and_options

def main():
    app, question_window, options_window = setup_ui()

    setup_hotkeys(
        question_window,
        options_window,
        lambda: process_question_and_options(question_window, options_window)
    )

    print("🎯 Tool ready (F8 to solve)")
    app.exec_()

if __name__ == "__main__":
    main()
