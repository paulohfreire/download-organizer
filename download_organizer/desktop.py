"""Small Windows desktop shell over the shared Organizer seam."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
import sys
from tkinter import filedialog, messagebox

from .cli import default_config_path
from .core import JsonConfigStore, JsonHistoryStore, Organizer, Rule, WindowsNotifier
from .watcher import WindowsFileWatcher
from .startup import WindowsStartup


def main() -> None:
    store = JsonConfigStore(default_config_path())
    organizer = Organizer(store.load(), store, JsonHistoryStore(default_config_path().with_name("history.json")), notifier=WindowsNotifier())
    root = tk.Tk()
    root.title("Download Organizer")
    folder = tk.StringVar(value=organizer.config.downloads_folder)
    unsorted = tk.StringVar(value=organizer.config.unsorted_folder)
    interval = tk.StringVar(value=str(organizer.config.scan_interval_seconds))
    allowed = tk.StringVar(value=";".join(organizer.config.allowed_locations))
    start_on_login = tk.BooleanVar(value=organizer.config.start_on_login)
    tk.Label(root, text="Downloads folder").grid(row=0, column=0, sticky="w")
    tk.Entry(root, textvariable=folder, width=55).grid(row=0, column=1)
    tk.Label(root, text="Unsorted folder").grid(row=1, column=0, sticky="w")
    tk.Entry(root, textvariable=unsorted, width=55).grid(row=1, column=1)
    tk.Label(root, text="Scan interval (seconds)").grid(row=2, column=0, sticky="w")
    tk.Entry(root, textvariable=interval, width=10).grid(row=2, column=1, sticky="w")
    status = tk.StringVar()
    tk.Label(root, textvariable=status).grid(row=5, column=0, columnspan=2, sticky="w")
    watcher: WindowsFileWatcher | None = None
    history = tk.Listbox(root, width=70, height=6)
    history.grid(row=6, column=2, rowspan=4, sticky="w")
    tk.Label(root, text="Move history").grid(row=5, column=2, sticky="w")
    history_filter = tk.StringVar()
    tk.Entry(root, textvariable=history_filter, width=15).grid(row=10, column=2, sticky="w")
    tk.Label(root, text="Rules").grid(row=6, column=0, sticky="nw")
    rules = tk.Listbox(root, width=70, height=6)
    rules.grid(row=6, column=1, rowspan=4, sticky="w")
    rule_name = tk.StringVar()
    rule_extension = tk.StringVar()
    rule_pattern = tk.StringVar(value="*")
    rule_destination = tk.StringVar()
    for row, (label, variable) in enumerate(
        (("Name", rule_name), ("Extension", rule_extension), ("Filename", rule_pattern), ("Destination", rule_destination)),
        start=10,
    ):
        tk.Label(root, text=label).grid(row=row, column=0, sticky="w")
        tk.Entry(root, textvariable=variable, width=55).grid(row=row, column=1, sticky="w")

    def refresh_rules() -> None:
        rules.delete(0, tk.END)
        for item in organizer.config.rules:
            rules.insert(tk.END, f"{item.name}: {item.extension or '*'} {item.filename_pattern} -> {item.destination}")

    def refresh_history() -> None:
        history.delete(0, tk.END)
        selected_kind = history_filter.get().strip() or None
        for item in organizer.move_history(selected_kind):
            history.insert(tk.END, f"{item.timestamp} {item.kind}: {item.source} -> {item.destination} ({item.reason})")

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

    def delete_rule() -> None:
        selection = rules.curselection()
        if selection:
            organizer.delete_rule(selection[0])
            refresh_rules()
            clear_rule_form()

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
            organizer.config.scan_interval_seconds = int(interval.get())
            organizer.config.allowed_locations = [item.strip() for item in allowed.get().split(";") if item.strip()]
            organizer.config.start_on_login = start_on_login.get()
            organizer.save_configuration()
            WindowsStartup(f'"{sys.executable}" -m download_organizer.desktop').set_enabled(organizer.config.start_on_login)
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
        refresh_history()

    def initial_scan() -> None:
        if save() and messagebox.askyesno("Initial scan", "Organize existing Downloads now?"):
            status.set(f"Initial scan observed {len(organizer.initial_scan(True))} Downloads")
            refresh_history()

    def rescan() -> None:
        status.set(f"Rescan observed {len(organizer.rescan())} Downloads")
        refresh_history()

    def export_config() -> None:
        target = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if target:
            try:
                organizer.export_configuration(Path(target))
            except ValueError as error:
                messagebox.showerror("Invalid configuration", str(error))

    def import_config() -> None:
        source = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if source:
            try:
                organizer.import_configuration(Path(source))
            except (ValueError, OSError) as error:
                messagebox.showerror("Invalid import", str(error))
                return
            folder.set(organizer.config.downloads_folder)
            unsorted.set(organizer.config.unsorted_folder)
            interval.set(str(organizer.config.scan_interval_seconds))
            allowed.set(";".join(organizer.config.allowed_locations))
            start_on_login.set(organizer.config.start_on_login)
            WindowsStartup(f'"{sys.executable}" -m download_organizer.desktop').set_enabled(organizer.config.start_on_login)
            refresh_rules()
            status.set("Configuration imported")

    def clear_history() -> None:
        organizer.clear_history()
        refresh_history()

    def start_watching() -> None:
        nonlocal watcher
        if not save():
            return
        try:
            watcher = WindowsFileWatcher(Path(folder.get()), lambda path: root.after(0, lambda: organizer.on_filesystem_event(path)))
            watcher.start()
        except RuntimeError as error:
            messagebox.showerror("Watcher unavailable", str(error))
            watcher = None
            return
        status.set("Watching Downloads")

        def scheduled_rescan() -> None:
            if watcher is not None:
                rescan()
                root.after(organizer.config.scan_interval_seconds * 1000, scheduled_rescan)

        root.after(organizer.config.scan_interval_seconds * 1000, scheduled_rescan)

    def stop_watching() -> None:
        nonlocal watcher
        if watcher is not None:
            watcher.stop()
            watcher = None
            status.set("Watcher stopped")

    tk.Button(root, text="Save", command=save).grid(row=3, column=0)
    tk.Button(root, text="Initial scan", command=initial_scan).grid(row=3, column=1, sticky="e")
    tk.Button(root, text="Rescan", command=rescan).grid(row=4, column=0)
    tk.Button(root, text="Start watching", command=start_watching).grid(row=4, column=1, sticky="w")
    tk.Button(root, text="Stop watching", command=stop_watching).grid(row=5, column=1, sticky="e")
    tk.Button(root, text="Add rule", command=add_rule).grid(row=11, column=0)
    tk.Button(root, text="Update rule", command=update_rule).grid(row=11, column=1, sticky="w")
    tk.Button(root, text="Move up", command=move_rule_up).grid(row=12, column=0)
    tk.Button(root, text="Move down", command=move_rule_down).grid(row=12, column=1, sticky="w")
    tk.Button(root, text="Delete rule", command=delete_rule).grid(row=13, column=0)
    tk.Button(root, text="Organize now", command=organize).grid(row=13, column=1, sticky="w")
    tk.Button(root, text="Filter history", command=refresh_history).grid(row=11, column=2)
    tk.Button(root, text="Clear history", command=clear_history).grid(row=12, column=2)
    tk.Label(root, text="Allowed locations (semicolon-separated)").grid(row=14, column=0, sticky="w")
    tk.Entry(root, textvariable=allowed, width=55).grid(row=14, column=1, columnspan=2, sticky="w")
    tk.Checkbutton(root, text="Start on login", variable=start_on_login).grid(row=15, column=0, sticky="w")
    tk.Button(root, text="Export config", command=export_config).grid(row=16, column=0)
    tk.Button(root, text="Import config", command=import_config).grid(row=16, column=1, sticky="w")
    rules.bind("<<ListboxSelect>>", select_rule)
    refresh_rules()
    refresh_history()
    root.protocol("WM_DELETE_WINDOW", lambda: (stop_watching(), root.destroy()))
    root.mainloop()
