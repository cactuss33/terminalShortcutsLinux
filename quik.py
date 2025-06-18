import os
import subprocess
import sys
import readline

# Colores ANSI
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

shortcuts = []

if os.geteuid() != 0:
    sys.exit(RED + "Please use sudo!" + RESET)

for file in os.listdir("/usr/local/bin/"):
    shortcuts.append(file)

print(BOLD + CYAN + "Welcome to the shortcut manager." + RESET)
print(CYAN + "Your current shortcuts are:" + RESET)
print(BLUE + str(shortcuts) + "\n" + RESET)

userChoose = input(
    GREEN + "If you want to add another -> +" + RESET + "\n" +
    RED + "If you want to delete one -> -" + RESET + "\n"
)
print()

def path_completer(text, state):
    text_expanded = os.path.expanduser(text)
    
    if not text_expanded:
        text_expanded = os.path.expanduser('~')
    
    dirname = os.path.dirname(text_expanded)
    basename = os.path.basename(text_expanded)
    
    if dirname == '':
        dirname = '.'
    
    try:
        entries = os.listdir(dirname)
    except FileNotFoundError:
        entries = []
    
    completions = []
    for entry in entries:
        if entry.startswith(basename):
            full_path = os.path.join(dirname, entry)
            display_path = full_path

            if full_path.startswith(os.path.expanduser('~')):
                display_path = '~' + full_path[len(os.path.expanduser('~')):]
            if os.path.isdir(full_path):
                display_path += '/'
            completions.append(display_path)
    
    try:
        return completions[state]
    except IndexError:
        return None

if userChoose == "+":
    name = " "
    while " " in name:
        name = input(CYAN + "Choose the shortcut name:\n" + RESET)
        if " " in name:
            print(RED + "The name cannot contain spaces" + RESET + "\n")
    print()
    
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(path_completer)

    path = input(CYAN + "Enter the executable file path:\n" + RESET)

    readline.set_completer(None)

    path = os.path.expanduser(path)

    pathWithoutFile = os.path.dirname(path)
    file = os.path.basename(path)
    shortcutPrep = f"cd {pathWithoutFile} && ./{file}"

    with open("prepare", "w") as prep:
        prep.write(shortcutPrep)
    
    subprocess.run("sudo cp prepare /usr/local/bin/", shell=True)
    subprocess.run(f"sudo mv /usr/local/bin/prepare /usr/local/bin/{name}", shell=True)
    subprocess.run(f"chmod +x /usr/local/bin/{name}", shell=True)

    print("\n" + GREEN + "Created!" + RESET)
    print(YELLOW + "You can do more things by running this again." + RESET)

elif userChoose == "-":
    name = input(RED + "Which shortcut do you want to remove?\n" + RESET)
    subprocess.run(f"sudo rm /usr/local/bin/{name}", shell=True)
    print("\n" + GREEN + "Completed!" + RESET)

else:
    print(BLUE + "Exit." + RESET)
