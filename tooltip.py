import tkinter as tk

class ToolTip:
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text          # String of lambda/functie
        self.delay = delay
        self.tip = None
        self.after_id = None

        widget.bind("<Enter>", self.enter)
        widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.after_id = self.widget.after(self.delay, self.show)

    def leave(self, event=None):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        self.hide()

    def show(self):
        if self.tip:
            return

        text = self.text() if callable(self.text) else self.text

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tip,
            text=text,
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            padx=5,
            pady=2,
            justify="left",
            wraplength=300
        )
        label.pack()

    def hide(self):
        if self.tip:
            self.tip.destroy()
            self.tip = None