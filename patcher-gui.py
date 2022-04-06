import sys
import logging
import tkinter as tk
import os
from tkinter import filedialog
from tkinter import messagebox

from src.patcher import *
from src.configuration import read_config, make_default_config, save_cfg, update_config
from src.pybinpatch import DiffPatch, WrongSourceFile

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
    
    # Patch the ISO
    # Should this be included in the gui or moved to patcher.py
    def patch(self):
        log.info(f"Input iso: {self.input_iso_path.path.get()}")
        log.info(f"Input track: {self.input_mod_path.path.get()}")
        log.info(f"Output iso: {self.output_iso_path.path.get()}")
        
        # If ISO or mod zip aren't provided, raise error
        if not self.input_iso_path.path.get():
            messagebox.showerror("Error", "You need to choose a MKDD ISO or GCM.")
            return 
        if not self.input_mod_path.get_paths():
            messagebox.showerror("Error", "You need to choose a MKDD Track/Mod zip file.")
            return 
        
        # Open iso and get first four bytes
        # Expected: GM4E / GM4P / GM4J
        with open(self.input_iso_path.path.get(), "rb") as f:
            gameid = f.read(4)
        
        # Display error if not a valid gameid
        if gameid not in GAMEID_TO_REGION:
            messagebox.showerror("Error", "Unknown Game ID: {}. Probably not a MKDD ISO.".format(gameid))
            return 
            
        # Get gameid
        region = GAMEID_TO_REGION[gameid]
        
        # Create GCM object with the ISO
        log.info("Patching now")
        isopath = self.input_iso_path.path.get()
        iso = GCM(isopath)
        iso.read_entire_disc()
        
        # Create ZipToIsoPatcher object
        patcher = ZipToIsoPatcher(None, iso)
        
        at_least_1_track = False 
        
        conflicts = Conflicts()
        
        skipped = 0

        code_patches = []

        for mod in self.input_mod_path.get_paths():
            log.info(mod)
            patcher.set_zip(mod)

            if patcher.is_code_patch():
                log.info("Found code patch")
                code_patches.append(mod)

        if len(code_patches) > 1:
            messagebox.showerror("Error",
                                 "More than one code patch selected:\n{}\nPlease only select one code patch.".format(
                                    "\n".join(os.path.basename(x) for x in code_patches)))

            return

        elif len(code_patches) == 1:
            patcher.set_zip(code_patches[0])
            patch_name = "codepatch_"+region+".bin"
            log.info("{0} exists? {1}".format(patch_name, patcher.src_file_exists(patch_name)))
            if patcher.src_file_exists(patch_name):
                patchfile = patcher.zip_open(patch_name)
                patch = DiffPatch.from_patch(patchfile)
                dol = patcher.get_iso_file("sys/main.dol")

                src = dol.read()
                dol.seek(0)
                try:
                    patch.apply(src, dol)
                    dol.seek(0)
                    patcher.change_file("sys/main.dol", dol)
                    log.info("Applied patch")
                except WrongSourceFile:
                    do_continue = messagebox.askyesno(
                        "Warning",
                        "The game executable has already been patched or is different than expected. "
                        "Patching it again may have unintended side effects (e.g. crashing) "
                        "so it is recommended to cancel patching and try again "
                        "on an unpatched, vanilla game ISO. \n\n"
                        "Do you want to continue?")

                    if not do_continue:
                        return
                    else:
                        patch.apply(src, dol, ignore_hash_mismatch=True)
                        dol.seek(0)
                        patcher.change_file("sys/main.dol", dol)
                        log.info("Applied patch, there may be side effects.")

        # Go through each mod path
        for mod in self.input_mod_path.get_paths():
            # Get mod zip
            log.info(mod)
            mod_name = os.path.basename(mod)
            patcher.set_zip(mod)

            if patcher.is_code_patch():
                continue
            
            
            config = configparser.ConfigParser()
            #log.info(trackzip.namelist())
            if patcher.src_file_exists("modinfo.ini"):
                
                modinfo = patcher.zip_open("modinfo.ini")
                config.read_string(str(modinfo.read(), encoding="utf-8"))
                log.info(f"Mod {config['Config']['modname']} by {config['Config']['author']}")
                log.info(f"Description: {config['Config']['description']}")
                # patch files 
                #log.info(trackzip.namelist())
                
                
                arcs, files = patcher.get_file_changes("files/")
                for filepath in files:
                    patcher.copy_file("files/"+filepath, "files/"+filepath)
                    conflicts.add_conflict(filepath, mod_name)
                
                for arc, arcfiles in arcs.items():
                    if arc == "race2d.arc":
                        continue 
                        
                    srcarcpath = "files/"+arc
                    if not iso.file_exists(srcarcpath):
                        continue 
                        
                    #log.info("Loaded arc:", arc)
                    destination_arc = Archive.from_file(patcher.get_iso_file(srcarcpath))

                    for file in arcfiles:
                        #log.info("files/"+file)
                        patcher.copy_file_into_arc("files/"+arc+"/"+file,
                                    destination_arc, file, missing_ok=False)
                        conflicts.add_conflict(arc+"/"+file, mod_name)

                    newarc = BytesIO()
                    destination_arc.write_arc_uncompressed(newarc)
                    newarc.seek(0)
                    
                    patcher.change_file(srcarcpath, newarc)
                
                if "race2d.arc" in arcs:
                    arcfiles = arcs["race2d.arc"]
                    #log.info("Loaded race2d arc")
                    mram_arc = Archive.from_file(patcher.get_iso_file("files/MRAM.arc"))
                    
                    race2d_arc = Archive.from_file(mram_arc["mram/race2d.arc"])
                    
                    for file in arcfiles:
                        patcher.copy_file_into_arc("files/race2d.arc/"+file,
                                    race2d_arc, file, missing_ok=False)
                        conflicts.add_conflict("race2d.arc/"+file, mod_name)
                    
                    race2d_arc_file = mram_arc["mram/race2d.arc"]
                    race2d_arc_file.seek(0)
                    race2d_arc.write_arc_uncompressed(race2d_arc_file)
                    #race2d_arc_file.truncate()

                    newarc = BytesIO()
                    mram_arc.write_arc_uncompressed(newarc)
                    newarc.seek(0)
                    
                    patcher.change_file("files/MRAM.arc", newarc)
                
            elif patcher.src_file_exists("trackinfo.ini"):
                at_least_1_track = True 
                trackinfo = patcher.zip_open("trackinfo.ini")
                config.read_string(str(trackinfo.read(), encoding="utf-8"))
                
                #use_extended_music = config.getboolean("Config", "extended_music_slots")
                replace = config["Config"]["replaces"].strip()
                replace_music = config["Config"]["replaces_music"].strip()
                
                log.info("Imported Track Info:")
                log.info(f"Track '{config['Config']['trackname']}' created by "
                         f"{config['Config']['author']} replaces {config['Config']['replaces']}")
                
                minimap_settings = json.load(patcher.zip_open("minimap.json"))
                
                conflicts.add_conflict(replace, mod_name)
                
                
                
                
                
                
                bigname, smallname = arc_mapping[replace]
                if replace in file_mapping:
                    _, _, bigbanner, smallbanner, trackname, trackimage = file_mapping[replace]
                else:
                    _, trackimage, trackname = battle_mapping[replace] 
                
                # Copy staff ghost 
                patcher.copy_file("staffghost.ght", "files/StaffGhosts/{}.ght".format(bigname))
                
                # Copy track arc 
                track_arc = Archive.from_file(patcher.zip_open("track.arc"))
                if patcher.src_file_exists("track_mp.arc"):
                    track_mp_arc = Archive.from_file(patcher.zip_open("track_mp.arc"))
                else:
                    track_mp_arc = Archive.from_file(patcher.zip_open("track.arc"))
                
                
                # Patch minimap settings in dol 
                dol = DolFile(patcher.get_iso_file("sys/main.dol"))
                patch_minimap_dol(dol, replace, region, minimap_settings,  
                intended_track=(track_arc.root.name==smallname))
                dol._rawdata.seek(0)
                patcher.change_file("sys/main.dol", dol._rawdata)
                
                patch_musicid(track_arc, replace_music)
                patch_musicid(track_mp_arc, replace_music)
                
                rename_archive(track_arc, smallname, False)
                rename_archive(track_mp_arc, smallname, True)
                
                newarc = BytesIO()
                track_arc.write_arc_uncompressed(newarc)
                
                newarc_mp = BytesIO()
                track_mp_arc.write_arc_uncompressed(newarc_mp)
                
                patcher.change_file("files/Course/{}.arc".format(bigname), newarc)
                patcher.change_file("files/Course/{}L.arc".format(bigname), newarc_mp)
             
                log.info(f"replacing files/Course/{bigname}.arc")
                
                
                if replace == "Luigi Circuit":
                    if patcher.src_file_exists("track_50cc.arc"):
                        patcher.copy_file("track_50cc.arc", "files/Course/Luigi.arc")
                    else:
                        rename_archive(track_arc, "luigi", False)
                        newarc = BytesIO()
                        track_arc.write_arc_uncompressed(newarc)
                        
                        patcher.change_file("files/Course/Luigi.arc", newarc)
                        
                    if patcher.src_file_exists("track_mp_50cc.arc"):
                        patcher.copy_file("track_mp_50cc.arc", "files/Course/LuigiL.arc")
                    else:
                        rename_archive(track_mp_arc, "luigi", True)
                        
                        newarc = BytesIO()
                        track_mp_arc.write_arc_uncompressed(newarc)
                        
                        patcher.change_file("files/Course/LuigiL.arc", newarc)
                        
                        
                if bigname == "Luigi2":
                    bigname = "Luigi"
                if smallname == "luigi2":
                    smallname = "luigi"
                # Copy language images 
                missing_languages = []
                main_language = config["Config"]["main_language"]
                
                for srclanguage in LANGUAGES:
                    dstlanguage = srclanguage
                    if not patcher.src_file_exists("course_images/{}/".format(srclanguage)):
                        #missing_languages.append(srclanguage)
                        #continue
                        srclanguage = main_language
                    
                    
                    coursename_arc_path = "files/SceneData/{}/coursename.arc".format(dstlanguage)
                    courseselect_arc_path = "files/SceneData/{}/courseselect.arc".format(dstlanguage)
                    lanplay_arc_path = "files/SceneData/{}/LANPlay.arc".format(dstlanguage)
                    mapselect_arc_path = "files/SceneData/{}/mapselect.arc".format(dstlanguage)
                    
                    if not iso.file_exists(coursename_arc_path):
                        continue 
                    
                    #log.info("Found language", language)
                    patcher.copy_file("course_images/{}/track_big_logo.bti".format(srclanguage),
                                        "files/CourseName/{}/{}_name.bti".format(dstlanguage, bigname))
                                        
                    if replace not in battle_mapping:
                        coursename_arc = Archive.from_file(patcher.get_iso_file(coursename_arc_path))
                        courseselect_arc = Archive.from_file(patcher.get_iso_file(courseselect_arc_path))
                        
                        patcher.copy_file_into_arc("course_images/{}/track_small_logo.bti".format(srclanguage),
                                    coursename_arc, "coursename/timg/{}_names.bti".format(smallname))
                        patcher.copy_file_into_arc("course_images/{}/track_name.bti".format(srclanguage),
                                    courseselect_arc, "courseselect/timg/{}".format(trackname))
                        patcher.copy_file_into_arc("course_images/{}/track_image.bti".format(srclanguage),
                                    courseselect_arc, "courseselect/timg/{}".format(trackimage))
                                    
                        newarc = BytesIO()
                        coursename_arc.write_arc_uncompressed(newarc)
                        newarc.seek(0)
                        
                        newarc_mp = BytesIO()
                        courseselect_arc.write_arc_uncompressed(newarc_mp)
                        newarc_mp.seek(0)
                    
                        patcher.change_file(coursename_arc_path, newarc)
                        patcher.change_file(courseselect_arc_path, newarc_mp)
                        
                    else:
                        mapselect_arc = Archive.from_file(patcher.get_iso_file(mapselect_arc_path))
                        
                        patcher.copy_file_into_arc("course_images/{}/track_name.bti".format(srclanguage),
                                    mapselect_arc, "mapselect/timg/{}".format(trackname))
                        patcher.copy_file_into_arc("course_images/{}/track_image.bti".format(srclanguage),
                                    mapselect_arc, "mapselect/timg/{}".format(trackimage))
                        
                        newarc_mapselect = BytesIO()
                        mapselect_arc.write_arc_uncompressed(newarc_mapselect)
                        newarc_mapselect.seek(0)
                    
                        patcher.change_file(mapselect_arc_path, newarc_mapselect)
                        
                        
                    lanplay_arc = Archive.from_file(patcher.get_iso_file(lanplay_arc_path))
                    patcher.copy_file_into_arc("course_images/{}/track_name.bti".format(srclanguage),
                                lanplay_arc, "lanplay/timg/{}".format(trackname))


                    newarc_lan = BytesIO()
                    lanplay_arc.write_arc_uncompressed(newarc_lan)
                    newarc_lan.seek(0)
                    
                    patcher.change_file(lanplay_arc_path, newarc_lan)                    
                
                
                # Copy over the normal and fast music
                # Note: if the fast music is missing, the normal music is used as fast music 
                # and vice versa. If both are missing, no copying is happening due to behaviour of
                # copy_or_add_file function
                if replace in file_mapping:
                    normal_music, fast_music = file_mapping[replace_music][0:2]
                    patcher.copy_or_add_file("lap_music_normal.ast", "files/AudioRes/Stream/{}".format(normal_music),
                        missing_ok=True)
                    patcher.copy_or_add_file("lap_music_fast.ast", "files/AudioRes/Stream/{}".format(fast_music),
                        missing_ok=True)
                    if not patcher.src_file_exists("lap_music_normal.ast"):
                        patcher.copy_or_add_file("lap_music_fast.ast", "files/AudioRes/Stream/{}".format(normal_music),
                            missing_ok=True)
                    if not patcher.src_file_exists("lap_music_fast.ast"):
                        patcher.copy_or_add_file("lap_music_normal.ast", "files/AudioRes/Stream/{}".format(fast_music),
                            missing_ok=True)
                    conflicts.add_conflict("music_"+replace_music, mod_name)
            else:
                log.warning("not a race track or mod, skipping...")
                skipped += 1
                
        if at_least_1_track:
            patch_baa(iso)
            
        log.info("patches applied")
        
        #log.info("all changed files:", iso.changed_files.keys())
        if conflicts.conflict_appeared:
            resulting_conflicts = conflicts.get_conflicts()
            warn_text = ("File change conflicts between mods were encountered.\n"
                "Conflicts between the following mods exist:\n\n")
            for i in range(min(len(resulting_conflicts), 5)):
                warn_text += "{0}. ".format(i+1) + ", ".join(resulting_conflicts[i])
                warn_text += "\n"
            if len(resulting_conflicts) > 5:
                warn_text += "And {} more".format(len(resulting_conflicts)-5)
            
            warn_text += ("\nIf you continue patching, the new ISO might be inconsistent. \n"
                "Do you want to continue patching? \n")

            do_continue = messagebox.askyesno("Warning",
                warn_text)
            
            if not do_continue:
                messagebox.showinfo("Info", "ISO patching cancelled.")
                return 
        log.info(f"writing iso to {self.output_iso_path.path.get()}")
        try:
            iso.export_disc_to_iso_with_changed_files(self.output_iso_path.path.get())
        except Exception as error:
            messagebox.showerror("Error", "Error while writing ISO: {0}".format(str(error)))
            raise 
        else:
            if skipped == 0:
                messagebox.showinfo("Info", "New ISO successfully created!")
            else:
                messagebox.showinfo("Info", ("New ISO successfully created!\n"
                    "{0} zip file(s) skipped due to not being race tracks or mods.".format(skipped)))
            
            log.info("finished writing iso, you are good to go!") 
        
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