"""Small Windows desktop shell over the shared Organizer seam."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from .cli import default_config_path
from .core import JsonConfigStore, JsonHistoryStore, Organizer, Rule, WindowsNotifier


def main() -> None:
    store = JsonConfigStore(default_config_path())
    organizer = Organizer(store.load(), store, JsonHistoryStore(default_config_path().with_name("history.json")), notifier=WindowsNotifier())
    root = tk.Tk()
    root.title("Download Organizer")
    folder = tk.StringVar(value=organizer.config.downloads_folder)
    unsorted = tk.StringVar(value=organizer.config.unsorted_folder)
    tk.Label(root, text="Downloads folder").grid(row=0, column=0, sticky="w")
    tk.Entry(root, textvariable=folder, width=55).grid(row=0, column=1)
    tk.Label(root, text="Unsorted folder").grid(row=1, column=0, sticky="w")
    tk.Entry(root, textvariable=unsorted, width=55).grid(row=1, column=1)
    status = tk.StringVar()
    tk.Label(root, textvariable=status).grid(row=4, column=0, columnspan=2, sticky="w")
    tk.Label(root, text="Rules").grid(row=5, column=0, sticky="nw")
    rules = tk.Listbox(root, width=70, height=6)
    rules.grid(row=5, column=1, rowspan=4, sticky="w")
    rule_name = tk.StringVar()
    rule_extension = tk.StringVar()
    rule_pattern = tk.StringVar(value="*")
    rule_destination = tk.StringVar()
    for row, (label, variable) in enumerate(
        (("Name", rule_name), ("Extension", rule_extension), ("Filename", rule_pattern), ("Destination", rule_destination)),
        start=9,
    ):
        tk.Label(root, text=label).grid(row=row, column=0, sticky="w")
        tk.Entry(root, textvariable=variable, width=55).grid(row=row, column=1, sticky="w")

    def refresh_rules() -> None:
        rules.delete(0, tk.END)
        for item in organizer.config.rules:
            rules.insert(tk.END, f"{item.name}: {item.extension or '*'} {item.filename_pattern} -> {item.destination}")

    def clear_rule_form() -> None:
        rule_name.set("")
        rule_extension.set("")
        rule_pattern.set("*")
        rule_destination.set("")

    def add_rule() -> None:
        try:
            organizer.add_rule(Rule(rule_name.get(), rule_extension.get(), rule_pattern.get(), rule_destination.get()))
        except ValueError as error:
            messagebox.showerror("Invalid rule", str(error))
            return
        refresh_rules()
        clear_rule_form()

    def select_rule(_event: object = None) -> None:
        selection = rules.curselection()
        if not selection:
            return
        item = organizer.config.rules[selection[0]]
        rule_name.set(item.name)
        rule_extension.set(item.extension)
        rule_pattern.set(item.filename_pattern)
        rule_destination.set(item.destination)

    def update_rule() -> None:
        selection = rules.curselection()
        if not selection:
            return
        try:
            organizer.update_rule(selection[0], Rule(rule_name.get(), rule_extension.get(), rule_pattern.get(), rule_destination.get()))
        except ValueError as error:
            messagebox.showerror("Invalid rule", str(error))
            return
        refresh_rules()

    def move_rule_up() -> None:
        selection = rules.curselection()
        if selection and selection[0] > 0:
            organizer.move_rule(selection[0], selection[0] - 1)
            refresh_rules()
            rules.selection_set(selection[0] - 1)

    def move_rule_down() -> None:
        selection = rules.curselection()
        if selection and selection[0] < len(organizer.config.rules) - 1:
            organizer.move_rule(selection[0], selection[0] + 1)
            refresh_rules()
            rules.selection_set(selection[0] + 1)

    def save() -> bool:
        organizer.config.downloads_folder = folder.get()
        organizer.config.unsorted_folder = unsorted.get()
        try:
            organizer.save_configuration()
        except ValueError as error:
            messagebox.showerror("Invalid configuration", str(error))
            return False
        status.set("Configuration saved")
        return True

    def organize() -> None:
        if not save():
            return
        results = organizer.organize_now()
        status.set(f"Organized {len(results)} Downloads")

    tk.Button(root, text="Save", command=save).grid(row=2, column=0)
    tk.Button(root, text="Add rule", command=add_rule).grid(row=10, column=0)
    tk.Button(root, text="Update rule", command=update_rule).grid(row=10, column=1, sticky="w")
    tk.Button(root, text="Move up", command=move_rule_up).grid(row=11, column=0)
    tk.Button(root, text="Move down", command=move_rule_down).grid(row=11, column=1, sticky="w")
    tk.Button(root, text="Organize now", command=organize).grid(row=3, column=0, columnspan=2)
    rules.bind("<<ListboxSelect>>", select_rule)
    refresh_rules()
    root.mainloop()
