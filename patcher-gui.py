import signal
import sys
import logging
import tkinter as tk
import os
from tkinter import filedialog
from tkinter import messagebox

from src.patcher import *
from src.configuration import (
    read_config,
    make_default_config,
    populate_default_config,
    save_cfg,
    update_config,
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="> %(message)s")
log = logging.getLogger(__name__)


# Windows for choosing a file path
class ChooseFilePath(tk.Frame):
    def __init__(self, master=None, description=None, file_chosen_callback=None, save=False, config=None):
        super().__init__(master)
        self.master = master
        self.pack(anchor="w")

        self.label = tk.Label(self, text=description, width=20, anchor="w")
        self.label.pack(side="left")
        self.path = tk.Entry(self)
        self.path.pack(side="left")
        self.button = tk.Button(self, text="Open", command=self.open_file)

        if save:
            self.button["text"] = "Save"

        self.button.pack(side="left")
        self.save = save
        self.callback = file_chosen_callback
        self.config = config

    def open_file(self):
        if self.config is not None:
            initialdir = self.config["default paths"]["iso"]
        else:
            initialdir = None

        if self.save:
            path = filedialog.asksaveasfilename(
                initialdir=initialdir,
                title="Choose location of new MKDD GCM/ISO",
                filetypes=(("GameCube Disc Image", "*.iso *.gcm"), ))
        else:
            path = filedialog.askopenfilename(
                initialdir=initialdir,
                title="Choose a MKDD GCM/ISO",
                filetypes=(("GameCube Disc Image", "*.iso *.gcm"), ))

        #log.info("path:" ,path)
        if path:
            self.path.delete(0, tk.END)
            self.path.insert(0, path)

            if self.callback is not None:
                self.callback(self)

            folder = os.path.dirname(path)
            if self.config is not None:
                self.config["default paths"]["iso"] = folder
                save_cfg(self.config)


# Window for choosing multiple file paths
class ChooseFilePathMultiple(tk.Frame):
    def __init__(self, master=None, description=None, save=False, config=None, folder=False):
        super().__init__(master)
        self.master = master
        self.pack(anchor="w")

        self.label = tk.Label(self, text=description, width=20, anchor="w")
        self.label.pack(side="left")
        self.path = tk.Entry(self)
        self.path.pack(side="left")
        self.button = tk.Button(self, text="Open", command=self.open_file)
        self.folder = folder

        if save:
            self.button["text"] = "Save"

        self.button.pack(side="left")
        self.save = save

        self.paths = []
        self.config = config

    def open_file(self):
        if self.config is not None:
            initialdir = self.config["default paths"]["mods"]
        else:
            initialdir = None

        if self.folder:
            paths = []
            folderpath = filedialog.askdirectory(
                initialdir=initialdir,
                title="Choose Race Track/Mod folder")
            for path in os.listdir(folderpath):
                joinedpath = os.path.join(folderpath, path)
                if os.path.isdir(joinedpath):
                    paths.append(joinedpath)

        else:
            paths = filedialog.askopenfilenames(
                initialdir=initialdir,
                title="Choose Race Track zip file(s)",
                filetypes=(("MKDD Track Zip", "*.zip"), ))

        #log.info("path:" ,path)
        if len(paths) > 0:
            self.path.delete(0, tk.END)
            self.path.insert(0, paths[0])
            self.paths = paths

        if len(paths) > 0:
            folder = os.path.dirname(paths[0])
            if self.config is not None:
                self.config["default paths"]["mods"] = folder
                save_cfg(self.config)

    def get_paths(self):
        if not self.path.get():
            return []
        elif self.path.get() not in self.paths:
            return [self.path.get()]
        else:
            return self.paths


# Main application
class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master

        self.pack()

        try:
            self.configuration = read_config()
            populate_default_config(self.configuration)
            log.info("Config file loaded")
            update_config(self.configuration)
        except FileNotFoundError as e:
            log.warning("No config file found, creating default config...")
            self.configuration = make_default_config()

        self.create_widgets()

    def make_open_button(self, master):
        button = tk.Button(master)
        button["text"] = "Open"
        return button

    def update_path(self, widget):
        if widget.path.get() and not self.output_iso_path.path.get():
            self.output_iso_path.path.delete(0, tk.END)
            self.output_iso_path.path.insert(0, widget.path.get()+"_new.iso")

    def create_widgets(self):
        self.input_iso_path = ChooseFilePath(self, description="MKDD ISO", file_chosen_callback=self.update_path,
            config=self.configuration)

        folder_mode = self.configuration.getboolean("options", "folder_mode")

        if folder_mode:
            self.input_mod_path = ChooseFilePathMultiple(self, description="Race track/Mod folder",
                                                         config=self.configuration, folder=True)
        else:
            self.input_mod_path = ChooseFilePathMultiple(self, description="Race track/Mod zip",
                                                         config=self.configuration)

        self.output_iso_path = ChooseFilePath(self, description="New ISO", save=True,
            config=self.configuration)

        self.frame = tk.Frame(self)
        self.frame.pack()
        self.patch_button = tk.Button(self.frame, text="Patch", command=self.patch)
        self.patch_button.pack()
        """self.hi_there = tk.Button(self)
        self.hi_there["text"] = "Hello World\n(click me)"
        self.hi_there["command"] = self.say_hi
        self.hi_there.pack(side="top")

        self.quit = tk.Button(self, text="QUIT", fg="red",
                              command=self.master.destroy)
        self.quit.pack(side="left")"""

    def patch(self):
        def message_callback(title: str, icon: str, text: str):
            _ = icon
            messagebox.showinfo(title, text)

        def prompt_callback(title: str, icon: str, text: str, buttons_labels: 'tuple[str]') -> bool:
            _ = icon, buttons_labels
            return messagebox.askyesno(title, text)

        def error_callback(title: str, icon: str, text: str):
            _ = icon
            messagebox.showerror(title, text)

        return patch(
            self.input_iso_path.path.get(),
            self.output_iso_path.path.get(),
            self.input_mod_path.get_paths(),
            message_callback,
            prompt_callback,
            error_callback,
        )

    def say_hi(self):
        log.info("hi there, everyone!")


class About(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.text = tk.Text(master, height=4)
        w.insert(1.0, "Hello World")
        w.pack()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    root = tk.Tk()
    root.geometry("350x150")
    def show_about():
        #about_text = "MKDD Patcher {0} by Yoshi2".format(VERSION)
        #about_text += "\nNew releases: https://github.com/RenolY2/mkdd-track-patcher/releases"
        #about_text += "\nReport bugs at: https://github.com/RenolY2/mkdd-track-patcher/issues"
        #messagebox.showinfo("About", about_text)
        about = tk.Toplevel(root)
        text = tk.Text(about, height=4)
        text.insert(1.0, "MKDD Patcher {0} by Yoshi2\n".format(VERSION))
        text.insert(2.0, "New releases: https://github.com/RenolY2/mkdd-track-patcher/releases\n")
        text.insert(3.0, "Post suggestions or bug reports at: https://github.com/RenolY2/mkdd-track-patcher/issues")
        text.pack()
        text.configure(state="disabled")

    root.title("MKDD Patcher")
    try:
        root.iconbitmap(str(pathlib.Path(__file__).parent.absolute()) + '/resources/icon.ico')
    except:
        pass
    menubar = tk.Menu(root)
    menubar.add_command(label="About", command=show_about)
    root.config(menu=menubar)
    app = Application(master=root)
    app.mainloop()