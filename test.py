#!/usr/bin/env python3
import os, sys, subprocess, threading, json, time, socket, getpass

# ---------------- Configuración ----------------
SHORTCUT_DIR = "/usr/local/bin"
DESKTOP_DIR = "/usr/share/applications"
PID_FILE = os.path.expanduser("~/.shortcut_manager_pids.json")
BUILD_DIR = "build"
APP_TEMPLATE = "appTemplate.desktop"  # Debes tener este archivo

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

USE_GUI = True
if "-noGui" in sys.argv:
    USE_GUI = False

# ---------------- Funciones auxiliares ----------------
def git_as_user(cmd, timeout=None, capture_output=False, env=None):
    user = os.environ.get("SUDO_USER", os.environ.get("USER"))
    base = ["sudo", "-u", user, "git"] + cmd
    if capture_output:
        out = subprocess.check_output(base, stderr=subprocess.STDOUT, timeout=timeout, env=env)
        return out.decode().strip()
    else:
        subprocess.run(base, check=True, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        return None

def has_internet(host="github.com", port=443, timeout=3):
    try:
        s = socket.create_connection((host, port), timeout)
        s.close()
        return True
    except:
        return False

def update_available():
    if not has_internet():
        return False
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        git_as_user(["fetch", "--quiet"], timeout=15, env=env)
        local = git_as_user(["rev-parse", "HEAD"], capture_output=True, timeout=10, env=env)
        remote = git_as_user(["rev-parse", "@{u}"], capture_output=True, timeout=10, env=env)
        return local != remote
    except:
        return False

def do_update():
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        print(YELLOW + "Updating..." + RESET)
        git_as_user(["pull", "--ff-only"], timeout=60, env=env)
        print(GREEN + "Update completed." + RESET)
    except Exception as e:
        print(RED + f"[!] git pull failed: {e}" + RESET)
    time.sleep(2)

def load_running_pids():
    if os.path.isfile(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_running_pids(data):
    with open(PID_FILE, "w") as f:
        json.dump(data, f)

def is_process_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except:
        return False

def create_shortcut(exec_path, name, icon_path=None):
    shortcut_prep = f"cd {os.path.dirname(exec_path)} && nice ./{os.path.basename(exec_path)} $@"
    os.makedirs(BUILD_DIR, exist_ok=True)
    with open(f"{BUILD_DIR}/commandBuild", "w") as f:
        f.write(shortcut_prep)
    subprocess.run(f"sudo cp {BUILD_DIR}/commandBuild {SHORTCUT_DIR}/{name}", shell=True)
    subprocess.run(f"chmod +x {SHORTCUT_DIR}/{name}", shell=True)
    if icon_path:
        with open(APP_TEMPLATE, "r") as template:
            content = template.read()
        content = content.replace("%exec%", name).replace("%icon%", icon_path)
        with open(f"{BUILD_DIR}/appBuild.desktop", "w") as f:
            f.write(content)
        subprocess.run(f"sudo cp {BUILD_DIR}/appBuild.desktop {DESKTOP_DIR}/{name}.desktop", shell=True)

def remove_shortcut(name):
    path = os.path.join(SHORTCUT_DIR, name)
    if os.path.isfile(path):
        subprocess.run(f"sudo rm {path}", shell=True)
    desktop = os.path.join(DESKTOP_DIR, f"{name}.desktop")
    if os.path.isfile(desktop):
        subprocess.run(f"sudo rm {desktop}", shell=True)

# ---------------- Terminal ----------------
if not USE_GUI:
    try:
        from prompt_toolkit import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.styles import Style
    except:
        subprocess.run("sudo apt install python3-prompt-toolkit -y", shell=True)
        print(GREEN + "prompt-toolkit installed. Run again." + RESET)
        sys.exit(1)

    # ---------------- FileBrowser completo ----------------
    class FileBrowser:
        def __init__(self, start_path=None):
            self.current_path = os.path.expanduser(start_path or "~")
            self.entries = []
            self.selected_index = 0
            self.message = ""
            self.update_entries()

            self.text_control = FormattedTextControl(self.get_formatted_text)
            self.window = Window(content=self.text_control, always_hide_cursor=True)

            self.kb = KeyBindings()
            self.kb_add_bindings()

            self.layout = Layout(HSplit([
                self.window,
                Window(height=1, char="-"),
                Window(height=1, content=FormattedTextControl(lambda: [("class:message", self.message)]))
            ]))

            self.style = Style.from_dict({
                "selected": "reverse",
                "directory": "ansiblue",
                "message": "ansicyan italic",
            })

            self.app = Application(layout=self.layout, key_bindings=self.kb, style=self.style, full_screen=False)

        def update_entries(self):
            try:
                entries = os.listdir(self.current_path)
            except Exception:
                entries = []
            entries = [e for e in entries if not e.startswith(".")]
            if os.path.dirname(self.current_path) != self.current_path:
                entries.insert(0, "..")
            self.entries = sorted(entries, key=lambda x: (not os.path.isdir(os.path.join(self.current_path, x)), x.lower()))
            if self.selected_index >= len(self.entries):
                self.selected_index = max(0, len(self.entries)-1)

        def get_formatted_text(self):
            result = [("class:directory", f" Current path: {self.current_path}\n\n")]
            if not self.entries:
                result.append(("", "No files or directories"))
                return result
            for i, entry in enumerate(self.entries):
                full_path = os.path.join(self.current_path, entry)
                style = "class:selected" if i == self.selected_index else ""
                if os.path.isdir(full_path):
                    display = entry + "/"
                    style += " class:directory"
                else:
                    display = entry
                result.append((style, display + "\n"))
            return result

        def kb_add_bindings(self):
            @self.kb.add("up")
            def up(event):
                if self.selected_index > 0:
                    self.selected_index -= 1

            @self.kb.add("down")
            def down(event):
                if self.selected_index < len(self.entries)-1:
                    self.selected_index += 1

            @self.kb.add("enter")
            def enter(event):
                selected = self.entries[self.selected_index]
                full_path = os.path.join(self.current_path, selected)
                if selected == "..":
                    self.current_path = os.path.dirname(self.current_path)
                    self.update_entries()
                elif os.path.isdir(full_path):
                    self.current_path = full_path
                    self.update_entries()
                else:
                    event.app.exit(result=os.path.realpath(full_path))

            @self.kb.add("backspace")
            def backspace(event):
                if os.path.dirname(self.current_path) != self.current_path:
                    self.current_path = os.path.dirname(self.current_path)
                    self.update_entries()

            @self.kb.add("escape")
            @self.kb.add("c-c")
            def exit_(event):
                event.app.exit(result=None)

        def run(self):
            subprocess.run("clear")
            result = self.app.run()
            subprocess.run("clear")
            return result

    def select_path_interactive(prompt_text="Select file or directory"):
        print(CYAN + f"{prompt_text} (Use arrows ↑↓, Enter to select/enter, Backspace to go back, ESC to cancel)" + RESET)
        home_user = os.path.join("/home", os.environ.get("SUDO_USER") or getpass.getuser())
        browser = FileBrowser(start_path=home_user)
        path = browser.run()
        if path is None:
            print(RED + "Selection cancelled." + RESET)
            sys.exit(1)
        return path

    # Terminal menu
    if update_available():
        if input(GREEN + "Update available, install? y/n " + RESET) == "y":
            do_update()

    shortcuts = [f for f in os.listdir(SHORTCUT_DIR)]
    print(BLUE + "Current shortcuts:" + RESET)
    print(shortcuts)

    choice = input(GREEN + "Add (+) or Remove (-)? " + RESET)
    if choice == "+":
        name = ""
        while not name or " " in name:
            name = input("Shortcut name (no spaces): ").strip()
        exec_path = select_path_interactive("Executable path")
        add_icon = input("Add icon? y/n: ").strip().lower()
        icon_path = select_path_interactive("Icon path") if add_icon == "y" else None
        create_shortcut(exec_path, name, icon_path)
        print(GREEN + "Shortcut created!" + RESET)
    elif choice == "-":
        name = input("Shortcut to remove: ").strip()
        remove_shortcut(name)
        print(GREEN + "Shortcut removed!" + RESET)
    else:
        print(BLUE + "Exit" + RESET)

# ---------------- GUI GTK ----------------
if USE_GUI:
    from gi.repository import Gtk, GLib

    class ShortcutManagerGTK(Gtk.Window):
        def __init__(self):
            super().__init__(title="Shortcut Manager")
            self.set_default_size(600, 400)
            self.running_shortcuts = load_running_pids()
            for k in list(self.running_shortcuts.keys()):
                pid = self.running_shortcuts[k].get("pid")
                if not is_process_alive(pid):
                    self.running_shortcuts.pop(k)

            self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            self.add(self.vbox)

            update_btn = Gtk.Button(label="Actualizar")
            update_btn.connect("clicked", lambda w: self.on_update())
            self.vbox.pack_start(update_btn, False, False, 5)

            scrolled = Gtk.ScrolledWindow()
            self.listbox = Gtk.ListBox()
            scrolled.add(self.listbox)
            self.vbox.pack_start(scrolled, True, True, 5)
            self.refresh_shortcuts()

        def refresh_shortcuts(self):
            self.listbox.foreach(lambda w: self.listbox.remove(w))
            shortcuts = sorted([f for f in os.listdir(SHORTCUT_DIR) if os.path.isfile(os.path.join(SHORTCUT_DIR, f))])
            for s in shortcuts:
                row = Gtk.ListBoxRow()
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                row.add(hbox)

                state_icon = Gtk.Image.new_from_icon_name("media-playback-start", Gtk.IconSize.MENU)
                hbox.pack_start(state_icon, False, False, 5)

                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                label_name = Gtk.Label(label=s, xalign=0)
                label_path = Gtk.Label(label=os.path.join(SHORTCUT_DIR, s), xalign=0)
                vbox.pack_start(label_name, False, False, 0)
                vbox.pack_start(label_path, False, False, 0)
                hbox.pack_start(vbox, True, True, 0)

                run_btn = Gtk.Button(label="▶")
                run_btn.connect("clicked", lambda btn, name=s, icon=state_icon: self.run_shortcut(name, btn, icon))
                hbox.pack_start(run_btn, False, False, 5)

                stop_btn = Gtk.Button(label="■")
                stop_btn.connect("clicked", lambda btn, name=s: self.stop_shortcut(name))
                hbox.pack_start(stop_btn, False, False, 5)

                self.listbox.add(row)
            self.listbox.show_all()

        def run_shortcut(self, shortcut_name, button, icon_widget):
            if self.running_shortcuts.get(shortcut_name, {}).get("process"):
                return
            button.set_sensitive(False)
            GLib.idle_add(icon_widget.set_from_icon_name, "process-stop", Gtk.IconSize.MENU)

            def target():
                try:
                    proc = subprocess.Popen(os.path.join(SHORTCUT_DIR, shortcut_name), shell=True)
                    self.running_shortcuts[shortcut_name] = {"process": proc, "pid": proc.pid, "thread": threading.current_thread()}
                    save_running_pids(self.running_shortcuts)
                    proc.wait()
                finally:
                    self.running_shortcuts.pop(shortcut_name, None)
                    save_running_pids(self.running_shortcuts)
                    GLib.idle_add(icon_widget.set_from_icon_name, "media-playback-start", Gtk.IconSize.MENU)
                    GLib.idle_add(button.set_sensitive, True)

            t = threading.Thread(target=target, daemon=True)
            t.start()

        def stop_shortcut(self, shortcut_name):
            entry = self.running_shortcuts.get(shortcut_name)
            if entry and entry.get("process"):
                entry["process"].terminate()

        def on_update(self):
            if update_available():
                do_update()
                self.refresh_shortcuts()

    win = ShortcutManagerGTK()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
