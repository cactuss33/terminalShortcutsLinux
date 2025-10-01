import os
import sys
import subprocess
import time
import socket
import getpass

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

try:
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.styles import Style
except:
    print(RED + "You are missing some libraries to install, they will be installed below:" + RESET)
    subprocess.run("sudo apt install python3-prompt-toolkit -y", shell=True)
    print(GREEN + "prompt-toolkit has been installed! Run the program again to apply the changes." + RESET)
    time.sleep(4)
    sys.exit()


def git_as_user(cmd, timeout=None, capture_output=False, env=None):
    """
    Ejecuta 'git <cmd>' como el usuario original (SUDO_USER o USER).
    """
    user = os.environ.get("SUDO_USER", os.environ.get("USER"))
    base = ["sudo", "-u", user, "git"] + cmd
    if capture_output:
        out = subprocess.check_output(base, stderr=subprocess.STDOUT, timeout=timeout, env=env)
        return out.decode().strip()
    else:
        subprocess.run(base, check=True, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        return None


def has_internet(host="github.com", port=443, timeout=3):
    """Comprueba conectividad TCP para evitar que git se cuelgue sin internet"""
    try:
        s = socket.create_connection((host, port), timeout)
        s.close()
        return True
    except Exception:
        return False


def update_available():
    if not has_internet():
        print(RED + "[!] No internet connection — skipping update check." + RESET)
        return False

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    try:
        git_as_user(["fetch", "--quiet"], timeout=15, env=env)
    except subprocess.TimeoutExpired:
        print(RED + "[!] git fetch timed out." + RESET)
        return False
    except subprocess.CalledProcessError as e:
        print(RED + f"[!] git fetch failed: {e}" + RESET)
        return False

    try:
        local = git_as_user(["rev-parse", "HEAD"], capture_output=True, timeout=10, env=env)
    except Exception:
        print(RED + "[!] Could not read local HEAD." + RESET)
        return False

    try:
        remoto = git_as_user(["rev-parse", "@{u}"], capture_output=True, timeout=10, env=env)
    except subprocess.CalledProcessError:
        print(RED + "[!] Remote branch not found (no upstream configured?)" + RESET)
        return False
    except subprocess.TimeoutExpired:
        print(RED + "[!] git rev-parse @{u} timed out." + RESET)
        return False

    return local != remoto


def do_update():
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    print(YELLOW + "Updating..." + RESET)
    try:
        git_as_user(["pull", "--ff-only"], timeout=60, env=env)
        print(GREEN + "Update completed." + RESET)
    except subprocess.TimeoutExpired:
        print(RED + "[!] git pull timed out." + RESET)
    except subprocess.CalledProcessError as e:
        print(RED + f"[!] git pull failed. Run 'git pull' manually to see the error: {e}" + RESET)
    time.sleep(2)


if update_available():
    if input(GREEN + "\nAn update is available right now, you want to install it? y/n " + RESET) == "y":
        do_update()
    else:
        print("ok")


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
            self.selected_index = max(0, len(self.entries) - 1)

    def get_formatted_text(self):
        result = []
        header = [("class:directory", f" Current path: {self.current_path}\n\n")]
        result.extend(header)

        if not self.entries:
            result.append(("", "No files or directories"))
            return result

        for i, entry in enumerate(self.entries):
            full_path = os.path.join(self.current_path, entry)
            if i == self.selected_index:
                style = "class:selected"
            else:
                style = ""

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
            if self.selected_index < len(self.entries) - 1:
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


if os.geteuid() != 0:
    print(RED + "Please run with sudo." + RESET)
    sys.exit(1)

subprocess.run("clear")

shortcuts = [file for file in os.listdir("/usr/local/bin/")]

print(BOLD + CYAN + "Welcome to the shortcut manager." + RESET)
print(CYAN + "Your current shortcuts are:" + RESET)
print(BLUE + str(shortcuts) + "\n" + RESET)

userChoose = input(
    GREEN + "If you want to add another -> +" + RESET + "\n" +
    RED + "If you want to delete one -> -" + RESET + "\n"
)
print()

if userChoose == "+":
    name = " "
    while " " in name or name == "":
        print(CYAN + "Choose the shortcut name" + RESET)
        name = input().strip()
        if " " in name or name == "":
            print(RED + "The name cannot contain spaces or be empty.\n" + RESET)

    print()

    path = select_path_interactive("Enter the executable file path")

    pathWithoutFile = os.path.dirname(path)
    file = os.path.basename(path)

    print(RED + "\nTrying to prioritize process for better performance...\n" + RESET)

    shortcutPrep = f"cd {pathWithoutFile} && nice ./{file} $@"

    os.makedirs("build", exist_ok=True)
    with open("build/commandBuild", "w") as prep:
        prep.write(shortcutPrep)

    subprocess.run("sudo cp build/commandBuild /usr/local/bin/", shell=True)
    subprocess.run(f"sudo mv /usr/local/bin/commandBuild /usr/local/bin/{name}", shell=True)
    subprocess.run(f"chmod +x /usr/local/bin/{name}", shell=True)

    print("\n" + GREEN + "Created!" + RESET)

    add_icon = input("Do you want to add an icon? y/n\n").strip().lower()
    if add_icon == "y":
        with open("appTemplate.desktop", "r") as template:
            content = template.read()

        content = content.replace("%exec%", name)

        iconPath = select_path_interactive("Enter the icon file path")

        content = content.replace("%icon%", iconPath)

        with open("build/appBuild.desktop", "w") as appBuild:
            appBuild.write(content)

        subprocess.run(f"cp build/appBuild.desktop /usr/share/applications/{name}.desktop", shell=True)
        print(GREEN + "\nCreated icon\n" + RESET)

    print(YELLOW + "You can do more things by running this again." + RESET)
    time.sleep(2.5)

elif userChoose == "-":
    print(RED + "Which shortcut do you want to remove?" + RESET)
    name = input().strip()
    subprocess.run(f"sudo rm /usr/local/bin/{name}", shell=True)

    desktop_file = f"/usr/share/applications/{name}.desktop"
    if os.path.isfile(desktop_file):
        subprocess.run(f"sudo rm {desktop_file}", shell=True)

    print("\n" + GREEN + "Completed!" + RESET)
    time.sleep(1.5)

else:
    print(BLUE + "Exit." + RESET)
    time.sleep(1.5)
