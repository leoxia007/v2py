# -*- coding: utf-8 -*-

from ui.main_window import V2rayClientApp

if __name__ == "__main__":
    app = V2rayClientApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
