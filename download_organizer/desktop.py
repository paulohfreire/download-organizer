"""Small Windows desktop shell over the shared Organizer seam."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cli import default_config_path
from .core import JsonConfigStore, JsonHistoryStore, Organizer, Rule, WindowsNotifier
from .startup import WindowsStartup, startup_command
from .watcher import WindowsFileWatcher


def main() -> None:
    store = JsonConfigStore(default_config_path())
    organizer = Organizer(
        store.load(),
        store,
        JsonHistoryStore(default_config_path().with_name("history.json")),
        notifier=WindowsNotifier(),
    )

    root = tk.Tk()
    root.title("Download Organizer")
    root.geometry("1220x820")
    root.minsize(980, 680)
    try:
        ttk.Style(root).theme_use("vista")
    except tk.TclError:
        pass

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    content = ttk.Frame(root, padding=(18, 16, 18, 10))
    content.grid(row=0, column=0, sticky="nsew")
    content.columnconfigure(0, weight=1)
    content.rowconfigure(3, weight=1)

    ttk.Label(content, text="Download Organizer", font=("Segoe UI", 20, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(
        content,
        text="Organize completed downloads safely with clear Rules and recoverable history.",
    ).grid(row=1, column=0, sticky="w", pady=(2, 14))

    folder = tk.StringVar(value=organizer.config.downloads_folder)
    unsorted = tk.StringVar(value=organizer.config.unsorted_folder)
    interval = tk.StringVar(value=str(organizer.config.scan_interval_seconds))
    allowed = tk.StringVar(value=";".join(organizer.config.allowed_locations))
    start_on_login = tk.BooleanVar(value=organizer.config.start_on_login)
    status = tk.StringVar(value="Ready. Save your settings to begin.")
    watcher: WindowsFileWatcher | None = None

    def choose_folder(variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory(title="Choose a folder")
        if selected:
            variable.set(selected)

    def add_allowed_location() -> None:
        selected = filedialog.askdirectory(title="Choose an allowed location")
        if selected:
            values = [item.strip() for item in allowed.get().split(";") if item.strip()]
            if selected not in values:
                values.append(selected)
            allowed.set(";".join(values))

    def set_status(message: str) -> None:
        status.set(message)

    configuration = ttk.LabelFrame(content, text="1. Configuration", padding=12)
    configuration.grid(row=2, column=0, sticky="ew", pady=(0, 12))
    configuration.columnconfigure(1, weight=1)

    def add_path_field(row: int, label: str, variable: tk.StringVar, explanation: str) -> None:
        ttk.Label(configuration, text=label, font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, sticky="nw", padx=(0, 12), pady=(0, 2)
        )
        ttk.Entry(configuration, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=(0, 2))
        ttk.Button(configuration, text="Browse…", command=lambda: choose_folder(variable)).grid(
            row=row, column=2, padx=(8, 0), pady=(0, 2)
        )
        ttk.Label(configuration, text=explanation).grid(
            row=row + 1, column=1, columnspan=2, sticky="w", pady=(0, 8)
        )

    add_path_field(0, "Downloads folder", folder, "Where new files arrive.")
    add_path_field(2, "Unsorted folder", unsorted, "Fallback destination when no Rule matches.")
    ttk.Label(configuration, text="Allowed locations", font=("Segoe UI", 10, "bold")).grid(
        row=4, column=0, sticky="nw", padx=(0, 12), pady=(0, 2)
    )
    ttk.Entry(configuration, textvariable=allowed).grid(row=4, column=1, sticky="ew", pady=(0, 2))
    ttk.Button(configuration, text="Add folder…", command=add_allowed_location).grid(
        row=4, column=2, padx=(8, 0), pady=(0, 2)
    )
    ttk.Label(configuration, text="Destinations must be inside one of these folders; separate paths with semicolons.").grid(
        row=5, column=1, columnspan=2, sticky="w", pady=(0, 8)
    )
    ttk.Label(configuration, text="Scan interval", font=("Segoe UI", 10, "bold")).grid(
        row=6, column=0, sticky="w", padx=(0, 12)
    )
    ttk.Spinbox(configuration, from_=1, to=86400, textvariable=interval, width=8).grid(
        row=6, column=1, sticky="w"
    )
    ttk.Label(configuration, text="seconds between automatic rescans").grid(row=6, column=1, sticky="w", padx=(90, 0))
    ttk.Checkbutton(configuration, text="Start watching automatically when I start the app", variable=start_on_login).grid(
        row=7, column=1, columnspan=2, sticky="w", pady=(8, 0)
    )

    rules_and_history = ttk.Frame(content)
    rules_and_history.grid(row=3, column=0, sticky="nsew")
    rules_and_history.columnconfigure(0, weight=1, uniform="panels")
    rules_and_history.columnconfigure(1, weight=1, uniform="panels")
    rules_and_history.rowconfigure(0, weight=1)

    rules_panel = ttk.LabelFrame(rules_and_history, text="2. Rules (first match wins)", padding=10)
    rules_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    rules_panel.columnconfigure(0, weight=1)
    rules_panel.rowconfigure(1, weight=1)
    ttk.Label(rules_panel, text="Example: PDF reports → Documents\\Reports").grid(row=0, column=0, sticky="w", pady=(0, 6))
    rules = tk.Listbox(rules_panel, height=8, width=52, activestyle="none", exportselection=False)
    rules.grid(row=1, column=0, sticky="nsew")
    rules_scroll = ttk.Scrollbar(rules_panel, orient="vertical", command=rules.yview)
    rules_scroll.grid(row=1, column=1, sticky="ns")
    rules.configure(yscrollcommand=rules_scroll.set)

    rule_name = tk.StringVar()
    rule_extension = tk.StringVar()
    rule_pattern = tk.StringVar(value="*")
    rule_destination = tk.StringVar()
    editor = ttk.LabelFrame(rules_panel, text="Rule editor", padding=8)
    editor.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    editor.columnconfigure(1, weight=1)

    def add_rule_field(row: int, label: str, variable: tk.StringVar, hint: str, browse: bool = False) -> None:
        ttk.Label(editor, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Entry(editor, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=2)
        if browse:
            ttk.Button(editor, text="Browse…", command=lambda: choose_folder(variable)).grid(row=row, column=2, padx=(6, 0))
        ttk.Label(editor, text=hint).grid(row=row + 1, column=1, columnspan=2, sticky="w", pady=(0, 3))

    add_rule_field(0, "Name", rule_name, "A label you will recognize.")
    add_rule_field(2, "Extension", rule_extension, "Optional, for example .pdf or jpg.")
    add_rule_field(4, "Filename", rule_pattern, "Optional wildcard, for example *invoice*.")
    add_rule_field(6, "Destination", rule_destination, "Folder where matching files should go.", browse=True)

    history_panel = ttk.LabelFrame(rules_and_history, text="3. Activity history", padding=10)
    history_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    history_panel.columnconfigure(0, weight=1)
    history_panel.rowconfigure(1, weight=1)
    ttk.Label(history_panel, text="Review Moves, skips, failures and Undo results.").grid(row=0, column=0, sticky="w", pady=(0, 6))
    history = tk.Listbox(history_panel, height=8, width=70, activestyle="none")
    history.grid(row=1, column=0, sticky="nsew")
    history_scroll = ttk.Scrollbar(history_panel, orient="vertical", command=history.yview)
    history_scroll.grid(row=1, column=1, sticky="ns")
    history.configure(yscrollcommand=history_scroll.set)
    history_filter = tk.StringVar()
    filter_bar = ttk.Frame(history_panel)
    filter_bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    ttk.Label(filter_bar, text="Filter kind:").pack(side="left")
    ttk.Entry(filter_bar, textvariable=history_filter, width=14).pack(side="left", padx=6)

    actions = ttk.LabelFrame(content, text="Actions", padding=10)
    actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
    for column in range(7):
        actions.columnconfigure(column, weight=1)

    def refresh_rules() -> None:
        rules.delete(0, tk.END)
        for index, item in enumerate(organizer.config.rules, start=1):
            rules.insert(tk.END, f"{index}. {item.name} | {item.extension or 'Any type'} | {item.filename_pattern} → {item.destination}")

    def refresh_history() -> None:
        history.delete(0, tk.END)
        selected_kind = history_filter.get().strip() or None
        for item in organizer.move_history(selected_kind):
            history.insert(tk.END, f"{item.timestamp} · {item.kind}: {item.source} → {item.destination} ({item.reason})")

    def clear_rule_form() -> None:
        rule_name.set("")
        rule_extension.set("")
        rule_pattern.set("*")
        rule_destination.set("")
        rules.selection_clear(0, tk.END)

    def add_rule() -> None:
        try:
            organizer.add_rule(Rule(rule_name.get(), rule_extension.get(), rule_pattern.get(), rule_destination.get()))
        except ValueError as error:
            messagebox.showerror("Invalid Rule", str(error))
            return
        refresh_rules()
        clear_rule_form()
        set_status("Rule added. Select Save to persist your changes.")

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
            set_status("Select a Rule first, then choose Update Rule.")
            return
        try:
            organizer.update_rule(selection[0], Rule(rule_name.get(), rule_extension.get(), rule_pattern.get(), rule_destination.get()))
        except ValueError as error:
            messagebox.showerror("Invalid Rule", str(error))
            return
        refresh_rules()
        set_status("Rule updated. Select Save to persist your changes.")

    def delete_rule() -> None:
        selection = rules.curselection()
        if selection:
            organizer.delete_rule(selection[0])
            refresh_rules()
            clear_rule_form()
            set_status("Rule deleted. Select Save to persist your changes.")
        else:
            set_status("Select a Rule first, then choose Delete Rule.")

    def move_rule_up() -> None:
        selection = rules.curselection()
        if selection and selection[0] > 0:
            organizer.move_rule(selection[0], selection[0] - 1)
            refresh_rules()
            rules.selection_set(selection[0] - 1)
            set_status("Rule moved up. Select Save to persist your changes.")

    def move_rule_down() -> None:
        selection = rules.curselection()
        if selection and selection[0] < len(organizer.config.rules) - 1:
            organizer.move_rule(selection[0], selection[0] + 1)
            refresh_rules()
            rules.selection_set(selection[0] + 1)
            set_status("Rule moved down. Select Save to persist your changes.")

    def save() -> bool:
        organizer.config.downloads_folder = folder.get()
        organizer.config.unsorted_folder = unsorted.get()
        try:
            organizer.config.scan_interval_seconds = int(interval.get())
            organizer.config.allowed_locations = [item.strip() for item in allowed.get().split(";") if item.strip()]
            organizer.config.start_on_login = start_on_login.get()
            organizer.save_configuration()
            WindowsStartup(startup_command()).set_enabled(organizer.config.start_on_login)
        except ValueError as error:
            messagebox.showerror("Invalid configuration", str(error))
            return False
        set_status("Configuration saved successfully.")
        return True

    def organize() -> None:
        if not save():
            return
        results = organizer.organize_now()
        moved = sum(item["status"] == "moved" for item in results)
        set_status(f"Organize now complete: {moved} moved, {len(results) - moved} other results.")
        refresh_history()

    def initial_scan() -> None:
        if save() and messagebox.askyesno("Initial scan", "Scan existing Downloads now? Files are moved after they are confirmed stable."):
            set_status(f"Initial scan recorded {len(organizer.initial_scan(True))} file observations. Run Rescan to continue.")
            refresh_history()

    def rescan() -> None:
        results = organizer.rescan()
        set_status(f"Rescan complete: {len(results)} file observations.")
        refresh_history()

    def export_config() -> None:
        target = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if target:
            try:
                organizer.export_configuration(Path(target))
            except ValueError as error:
                messagebox.showerror("Invalid configuration", str(error))
                return
            set_status(f"Configuration exported to {target}.")

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
            WindowsStartup(startup_command()).set_enabled(organizer.config.start_on_login)
            refresh_rules()
            set_status("Configuration imported successfully.")

    def clear_history() -> None:
        if messagebox.askyesno("Clear history", "Clear all local activity history? This cannot be undone."):
            organizer.clear_history()
            refresh_history()
            set_status("Activity history cleared.")

    def start_watching() -> None:
        nonlocal watcher
        if watcher is not None:
            set_status("Watcher is already running.")
            return
        if not save():
            return
        try:
            watcher = WindowsFileWatcher(Path(folder.get()), lambda path: root.after(0, lambda: organizer.on_filesystem_event(path)))
            watcher.start()
        except RuntimeError as error:
            messagebox.showerror("Watcher unavailable", str(error))
            watcher = None
            return
        set_status("Watching Downloads for new files.")

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
            set_status("Watcher stopped.")

    ttk.Button(actions, text="Save settings", command=save).grid(row=0, column=0, padx=3, sticky="ew")
    ttk.Button(actions, text="Initial scan", command=initial_scan).grid(row=0, column=1, padx=3, sticky="ew")
    ttk.Button(actions, text="Rescan", command=rescan).grid(row=0, column=2, padx=3, sticky="ew")
    ttk.Button(actions, text="Start watching", command=start_watching).grid(row=0, column=3, padx=3, sticky="ew")
    ttk.Button(actions, text="Stop watching", command=stop_watching).grid(row=0, column=4, padx=3, sticky="ew")
    ttk.Button(actions, text="Organize now", command=organize).grid(row=0, column=5, padx=3, sticky="ew")
    ttk.Button(actions, text="Add Rule", command=add_rule).grid(row=1, column=0, padx=3, pady=(8, 0), sticky="ew")
    ttk.Button(actions, text="Update Rule", command=update_rule).grid(row=1, column=1, padx=3, pady=(8, 0), sticky="ew")
    ttk.Button(actions, text="Move up", command=move_rule_up).grid(row=1, column=2, padx=3, pady=(8, 0), sticky="ew")
    ttk.Button(actions, text="Move down", command=move_rule_down).grid(row=1, column=3, padx=3, pady=(8, 0), sticky="ew")
    ttk.Button(actions, text="Delete Rule", command=delete_rule).grid(row=1, column=4, padx=3, pady=(8, 0), sticky="ew")
    ttk.Button(actions, text="Filter history", command=refresh_history).grid(row=1, column=5, padx=3, pady=(8, 0), sticky="ew")
    ttk.Button(actions, text="Clear history", command=clear_history).grid(row=1, column=6, padx=3, pady=(8, 0), sticky="ew")
    ttk.Button(actions, text="Export config", command=export_config).grid(row=2, column=0, padx=3, pady=(8, 0), sticky="ew")
    ttk.Button(actions, text="Import config", command=import_config).grid(row=2, column=1, padx=3, pady=(8, 0), sticky="ew")
    ttk.Label(actions, textvariable=status, foreground="#24527a").grid(row=2, column=2, columnspan=5, sticky="w", padx=(12, 3), pady=(8, 0))

    rules.bind("<<ListboxSelect>>", select_rule)
    refresh_rules()
    refresh_history()
    root.protocol("WM_DELETE_WINDOW", lambda: (stop_watching(), root.destroy()))
    root.mainloop()
