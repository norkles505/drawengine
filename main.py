import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.start_screen import StartScreen


def main():
    app = QApplication(sys.argv)

    start = StartScreen()
    if start.exec() != StartScreen.DialogCode.Accepted:
        # El usuario cerró la pantalla de inicio sin elegir nada.
        sys.exit(0)

    if start.result_action == "open":
        window = MainWindow()
        window._open_project_path(start.result_path)
    elif start.result_action == "new":
        window = MainWindow(
            start.result_width, start.result_height, start.result_fps)
    else:
        window = MainWindow()

    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
