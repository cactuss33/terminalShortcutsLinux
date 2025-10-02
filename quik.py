import signal
import os
import sys
import subprocess
import time
import getpass
import socket
import threading


subprocess.run("sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0",shell=True)



# ---------------- Modo de ejecución ----------------
USE_GUI = "-noGui" not in sys.argv

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

SHORTCUT_DIR = "/usr/local/bin/"
DESKTOP_DIR = "/usr/share/applications/"

# ---------------- Funciones compartidas ----------------
def git_as_user(cmd, timeout=None, capture_output=False, env=None):
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
    try:
        s = socket.create_connection((host, port), timeout)
        s.close()
        return True
    except Exception:
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
    except Exception:
        return False

def do_update():
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        git_as_user(["pull", "--ff-only"], timeout=60, env=env)
        print(GREEN + "Update completed." + RESET)
    except Exception:
        print(RED + "[!] Update failed." + RESET)
    time.sleep(2)

# ---------------- Funciones de shortcuts ----------------
def create_shortcut(exec_path, name, icon_path=None):
    if not os.path.isfile(exec_path) or not os.access(exec_path, os.X_OK):
        print(RED + f"Error: '{exec_path}' no existe o no es ejecutable" + RESET)
        return False
    if not name or " " in name:
        print(RED + "Error: el nombre del shortcut no puede estar vacío ni contener espacios" + RESET)
        return False
    os.makedirs("build", exist_ok=True)
    path_without_file = os.path.dirname(exec_path)
    file_name = os.path.basename(exec_path)
    shortcut_prep = f"cd {path_without_file} && nice ./{file_name} $@"
    with open("build/commandBuild", "w") as prep:
        prep.write(shortcut_prep)
    subprocess.run(f"sudo cp build/commandBuild {SHORTCUT_DIR}{name}", shell=True)
    subprocess.run(f"sudo chmod +x {SHORTCUT_DIR}{name}", shell=True)

    if icon_path and os.path.isfile("appTemplate.desktop"):
        with open("appTemplate.desktop", "r") as template:
            content = template.read()
        content = content.replace("%exec%", name)
        content = content.replace("%icon%", icon_path)
        with open("build/appBuild.desktop", "w") as f:
            f.write(content)
        subprocess.run(f"sudo cp build/appBuild.desktop {DESKTOP_DIR}{name}.desktop", shell=True)
    return True

def remove_shortcut(name):
    if os.path.isfile(f"{SHORTCUT_DIR}{name}"):
        subprocess.run(f"sudo rm {SHORTCUT_DIR}{name}", shell=True)
    desktop_file = f"{DESKTOP_DIR}{name}.desktop"
    if os.path.isfile(desktop_file):
        subprocess.run(f"sudo rm {desktop_file}", shell=True)




# ---------------- Modo GUI moderno ----------------
if USE_GUI:
            
    # ---------------- Ahora sí podemos importar GTK ----------------
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, Gdk, GLib, Gio, abcd
    except ImportError:
        subprocess.run("sudo apt update", shell=True)
        subprocess.run("sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0", shell=True)
        
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, Gdk, GLib, Gio
    
    class ShortcutManagerGTK(Gtk.Window):
        def __init__(self):
            super().__init__(title="Shortcut Manager")
            self.running_shortcuts = {}  # Llevará el estado de cada shortcut
            self.set_default_size(700, 500)
            self.set_border_width(10)

            # CSS moderno con hover
            css = b"""
            .shortcut-row { padding: 5px; border-bottom: 1px solid #ccc; }
            .shortcut-row:hover { background-color: #e0e0e0; }
            .shortcut-name { font-weight: bold; font-size: 14px; }
            .shortcut-path { font-size: 11px; color: #555; }
            """
            style_provider = Gtk.CssProvider()
            style_provider.load_from_data(css)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), style_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_USER
            )

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            self.add(vbox)

            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            vbox.pack_start(scrolled, True, True, 0)

            self.listbox = Gtk.ListBox()
            self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
            scrolled.add(self.listbox)

            hbox = Gtk.Box(spacing=10)
            vbox.pack_start(hbox, False, False, 0)

            add_btn = Gtk.Button(label="Add Shortcut")
            add_btn.connect("clicked", self.on_add)
            hbox.pack_start(add_btn, True, True, 0)

            remove_btn = Gtk.Button(label="Remove Shortcut")
            remove_btn.connect("clicked", self.on_remove)
            hbox.pack_start(remove_btn, True, True, 0)

            update_btn = Gtk.Button(label="Check for Updates")
            update_btn.connect("clicked", self.on_update)
            hbox.pack_start(update_btn, True, True, 0)

            GLib.idle_add(self.check_update_startup)
            self.refresh_shortcuts()

        def refresh_shortcuts(self):
            self.listbox.foreach(lambda w: self.listbox.remove(w))
            shortcuts = sorted([f for f in os.listdir(SHORTCUT_DIR) if os.path.isfile(os.path.join(SHORTCUT_DIR, f))])
        
            for s in shortcuts:
                row = Gtk.ListBoxRow()
                row.get_style_context().add_class("shortcut-row")
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                row.add(hbox)
        
                # Icono de estado (verde por defecto)
                state_icon = Gtk.Image.new_from_icon_name("media-playback-start", Gtk.IconSize.MENU)
                hbox.pack_start(state_icon, False, False, 5)
                
                desktop_file = os.path.join(DESKTOP_DIR, f"{s}.desktop")
                icon_path = None
                if os.path.isfile(desktop_file):
                    # Intentar leer el icono desde el .desktop
                    gfile = Gio.File.new_for_path(desktop_file)
                    info = gfile.query_info("standard::icon", Gio.FileQueryInfoFlags.NONE, None)
                    icon = info.get_icon()
                    if icon:
                        try:
                            # Intenta usar gicon
                            theme_icon = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.MENU)
                            theme_icon.set_pixel_size(32)  # Ajustar tamaño
                            hbox.pack_start(theme_icon, False, False, 5)
                        except Exception:
                            # Fallback: icono genérico si falla
                            fallback = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.MENU)
                            hbox.pack_start(fallback, False, False, 5)
                    else:
                        # Fallback si no hay icono
                        fallback = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.MENU)
                        hbox.pack_start(fallback, False, False, 5)
                else:
                    # Fallback si no existe .desktop
                    fallback = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.MENU)
                    hbox.pack_start(fallback, False, False, 5)
                
                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                hbox.pack_start(vbox, True, True, 0)
        
                label_name = Gtk.Label(label=s, xalign=0)
                label_name.get_style_context().add_class("shortcut-name")
                vbox.pack_start(label_name, False, False, 0)
        
                label_path = Gtk.Label(label=os.path.join(SHORTCUT_DIR, s), xalign=0)
                label_path.get_style_context().add_class("shortcut-path")
                vbox.pack_start(label_path, False, False, 0)
        
                # Botón ejecutar
                run_btn = Gtk.Button()
                play_icon = Gtk.Image.new_from_icon_name("media-playback-start", Gtk.IconSize.BUTTON)
                run_btn.set_image(play_icon)
                run_btn.set_always_show_image(True)

                hbox.pack_start(run_btn, False, False, 5)
        
                def run_shortcut(button, shortcut_name, shortcut_path, running_shortcuts):
                    if running_shortcuts.get(shortcut_name):
                        # Terminar el proceso
                        proc = running_shortcuts[shortcut_name]
                        if proc.poll() is None:  # sigue corriendo
                            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)  # termina toda la group
                            print(f"Stopped {shortcut_name}")
                        return
                
                    # Cambiar icono del botón
                    icon_widget = button.get_image()
                    icon_widget.set_from_icon_name("process-stop", Gtk.IconSize.BUTTON)
                
                    # Lanzar proceso en su propio grupo de procesos
                    proc = subprocess.Popen(
                        shortcut_path,
                        shell=True,             # importante para scripts
                        preexec_fn=os.setsid
                    )
                    
                
                    running_shortcuts[shortcut_name] = proc
                
                    # Hilo que espera a que termine
                    def monitor():
                        proc.wait()
                        GLib.idle_add(icon_widget.set_from_icon_name, "media-playback-start", Gtk.IconSize.BUTTON)
                        running_shortcuts.pop(shortcut_name, None)
                
                    threading.Thread(target=monitor, daemon=True).start()
        
                run_btn.connect(
                    "clicked",
                    lambda btn, s=s: run_shortcut(btn, shortcut_name=s, shortcut_path=os.path.join(SHORTCUT_DIR, s), running_shortcuts=self.running_shortcuts)
                )
            
                self.listbox.add(row)
            self.listbox.show_all()

        def on_add(self, widget):
            dialog = Gtk.FileChooserDialog(title="Select Executable", parent=self, action=Gtk.FileChooserAction.OPEN)
            dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
            if dialog.run() == Gtk.ResponseType.OK:
                exec_path = dialog.get_filename()
            else:
                dialog.destroy()
                return
            dialog.destroy()

            name_dialog = Gtk.Dialog(title="Shortcut Name", parent=self)
            box = name_dialog.get_content_area()
            entry = Gtk.Entry()
            entry.set_placeholder_text("Shortcut name")
            box.add(entry)
            name_dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            name_dialog.add_button("OK", Gtk.ResponseType.OK)
            name_dialog.show_all()
            if name_dialog.run() == Gtk.ResponseType.OK:
                name = entry.get_text().strip()
            else:
                name_dialog.destroy()
                return
            name_dialog.destroy()

            if not name or " " in name:
                error = Gtk.MessageDialog(parent=self, flags=0,
                                          message_type=Gtk.MessageType.ERROR,
                                          buttons=Gtk.ButtonsType.CLOSE,
                                          text="Invalid shortcut name")
                error.run()
                error.destroy()
                return

            icon_path = None
            icon_dialog = Gtk.MessageDialog(parent=self, flags=0,
                                            message_type=Gtk.MessageType.QUESTION,
                                            buttons=Gtk.ButtonsType.YES_NO,
                                            text="Do you want to add an icon?")
            if icon_dialog.run() == Gtk.ResponseType.YES:
                dialog = Gtk.FileChooserDialog(title="Select Icon", parent=self, action=Gtk.FileChooserAction.OPEN)
                dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
                if dialog.run() == Gtk.ResponseType.OK:
                    icon_path = dialog.get_filename()
                dialog.destroy()
            icon_dialog.destroy()
            create_shortcut(exec_path, name, icon_path)
            self.refresh_shortcuts()

        def on_remove(self, widget):
            selection = self.listbox.get_selected_row()
            if not selection:
                return
            vbox = selection.get_child().get_children()[1]  # el VBox de labels
            name = vbox.get_children()[0].get_text()
            confirm = Gtk.MessageDialog(parent=self, flags=0,
                                        message_type=Gtk.MessageType.QUESTION,
                                        buttons=Gtk.ButtonsType.YES_NO,
                                        text=f"Do you want to remove '{name}'?")
            if confirm.run() == Gtk.ResponseType.YES:
                remove_shortcut(name)
            confirm.destroy()
            self.refresh_shortcuts()

        def on_update(self, widget=None):
            if update_available():
                dialog = Gtk.MessageDialog(parent=self, flags=0,
                                           message_type=Gtk.MessageType.QUESTION,
                                           buttons=Gtk.ButtonsType.YES_NO,
                                           text="An update is available. Install it?")
                if dialog.run() == Gtk.ResponseType.YES:
                    do_update()
                dialog.destroy()
                self.refresh_shortcuts()
            else:
                info = Gtk.MessageDialog(parent=self, flags=0,
                                         message_type=Gtk.MessageType.INFO,
                                         buttons=Gtk.ButtonsType.OK,
                                         text="No updates available.")
                info.run()
                info.destroy()

        def check_update_startup(self):
            self.on_update()
            return False

    win = ShortcutManagerGTK()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

# ---------------- Modo Terminal ----------------
else:
    if update_available():
        if input(GREEN + "\nAn update is available. Install it? y/n " + RESET) == "y":
            do_update()
    subprocess.run("clear")
    shortcuts = [file for file in os.listdir(SHORTCUT_DIR)]
    print(BOLD + CYAN + "Shortcut Manager (Terminal Mode)" + RESET)
    print(CYAN + "Shortcuts:" + RESET)
    print(BLUE + str(shortcuts) + "\n" + RESET)

    userChoose = input(GREEN + "Add -> +\n" + RED + "Remove -> -\n" + RESET)
    if userChoose == "+":
        name = ""
        while " " in name or name == "":
            name = input(CYAN + "Shortcut name: " + RESET).strip()
        exec_path = input(CYAN + "Executable path: " + RESET).strip()
        icon_path = None
        if input("Add icon? y/n: ").strip().lower() == "y":
            icon_path = input(CYAN + "Icon path: " + RESET).strip()
        create_shortcut(exec_path, name, icon_path)
        print(GREEN + "Created!" + RESET)
    elif userChoose == "-":
        name = input(RED + "Shortcut to remove: " + RESET).strip()
        remove_shortcut(name)
        print(GREEN + "Removed!" + RESET)
    else:
        print(BLUE + "Exit." + RESET)
        time.sleep(1.5)
