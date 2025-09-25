import os
import sys
import subprocess
import time

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

def update_available():
    # Search for updates
    subprocess.run(["git", "fetch"], check=True)
    
    local = subprocess.check_output(["git", "rev-parse", "HEAD"]).strip()
    remoto = subprocess.check_output(["git", "rev-parse", "@{u}"]).strip()

    return local != remoto

if update_available:
    if input("An update is available right now, you want to install it? y/n") == "y":
        print("updating...")
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
        # Filtrar ocultos (archivos que empiezan con .)
        entries = [e for e in entries if not e.startswith(".")]
        if os.path.dirname(self.current_path) != self.current_path:
            entries.insert(0, "..")
        # Directorios primero, luego archivos, orden alfabético
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
        subprocess.run("clear")  # limpia pantalla antes de iniciar
        result = self.app.run()
        subprocess.run("clear")  # limpia pantalla al salir
        return result


def select_path_interactive(prompt_text="Select file or directory"):
    print(CYAN + f"{prompt_text} (Use arrows ↑↓, Enter to select/enter, Backspace to go back, ESC to cancel)" + RESET)
    home_user = os.path.join("/home", os.getlogin())
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
