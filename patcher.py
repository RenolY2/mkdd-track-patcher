import tkinter as tk
import zipfile
import json 
import configparser
import os 
import struct 
from io import BytesIO
from tkinter import filedialog
from tkinter import messagebox


from gcm import GCM
from track_mapping import music_mapping, arc_mapping, file_mapping, bsft, battle_mapping
from dolreader import *
from rarc import Archive, write_pad32, write_uint32
from readbsft import BSFT
from zip_helper import ZipToIsoPatcher
from configuration import read_config, make_default_config, save_cfg
from conflict_checker import Conflicts 

GAMEID_TO_REGION = {
    b"GM4E": "US",
    b"GM4P": "PAL",
    b"GM4J": "JP"
}

LANGUAGES = ["English", "Japanese", "German", "Italian", "French", "Spanish"]



def copy_if_not_exist(iso, newfile, oldfile):
    if not iso.file_exists("files/"+newfile):
        iso.add_new_file("files/"+newfile, iso.read_file_data("files/"+oldfile))


def patch_musicid(arc, new_music):
    if new_music in music_mapping:
        new_id = music_mapping[new_music]
        
        for filename in arc.root.files:
            if filename.endswith("_course.bol"):
                data = arc.root.files[filename]
                data.seek(0x19)
                id = data.read(1)[0]
                if id in music_mapping.values():
                    data.seek(0x19)
                    data.write(struct.pack("B", new_id))
                    data.seek(0x0)
               


def patch_baa(iso):
    baa = iso.read_file_data("files/AudioRes/GCKart.baa")
    baadata = baa.read()
    
    if b"COURSE_YCIRCUIT_0" in baadata:
        return # Baa is already patched, nothing to do
    
    bsftoffset = baadata.find(b"bsft")
    assert bsftoffset < 0x100
    
    baa.seek(len(baadata))
    new_bsft = BSFT()
    new_bsft.tracks = bsft
    write_pad32(baa)
    bsft_offset = baa.tell()
    new_bsft.write_to_file(baa)
    
    write_pad32(baa)
    baa.seek(bsftoffset)
    magic = baa.read(4)
    assert magic == b"bsft"
    write_uint32(baa, bsft_offset)
    iso.changed_files["files/AudioRes/GCKart.baa"] = baa
    print("patched baa")
    
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_YCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/COURSE_CIRCUIT_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_MCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/COURSE_CIRCUIT_0.x.32.c4.ast")
    

    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_CITY_0.x.32.c4.ast", "AudioRes/Stream/COURSE_HIWAY_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_COLOSSEUM_0.x.32.c4.ast", "AudioRes/Stream/COURSE_STADIUM_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_MOUNTAIN_0.x.32.c4.ast", "AudioRes/Stream/COURSE_JUNGLE_0.x.32.c4.ast")
    
    
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_YCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_CIRCUIT_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_MCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_CIRCUIT_0.x.32.c4.ast")
    

    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_CITY_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_HIWAY_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_COLOSSEUM_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_STADIUM_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_MOUNTAIN_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_JUNGLE_0.x.32.c4.ast")
    
    print("Copied ast files")
    
def patch_minimap_dol(dol, track, region, minimap_setting, intended_track=True):
    with open("resources/minimap_locations.json", "r") as f:
        addresses_json = json.load(f)
        addresses = addresses_json[region]
        corner1x, corner1z, corner2x, corner2z, orientation = addresses[track]

    orientation_val = minimap_setting["Orientation"]
    if orientation_val not in (0, 1, 2, 3):
        raise RuntimeError(
            "Invalid Orientation value: Must be in the range 0-3 but is {0}".format(orientation_val))

    dol.seek(int(orientation, 16))
    orientation_val = read_load_immediate_r0(dol)
    if orientation_val not in (0, 1, 2, 3):
        raise RuntimeError(
            "Wrong Address, orientation value in DOL isn't in 0-3 range: {0}. Maybe you are using"
            " a dol from a different game version?".format(orientation_val))

    dol.seek(int(orientation, 16))
    write_load_immediate_r0(dol, minimap_setting["Orientation"])
    dol.seek(int(corner1x, 16))
    write_float(dol, minimap_setting["Top Left Corner X"])
    dol.seek(int(corner1z, 16))
    write_float(dol, minimap_setting["Top Left Corner Z"])
    dol.seek(int(corner2x, 16))
    write_float(dol, minimap_setting["Bottom Right Corner X"])
    dol.seek(int(corner2z, 16))
    write_float(dol, minimap_setting["Bottom Right Corner Z"])
    
    if not intended_track:
        minimap_transforms = addresses_json[region+"_MinimapLocation"]
        if track in minimap_transforms:
            if len(minimap_transforms[track]) == 9:
                p1_offx, p1_offy, p1_scale = minimap_transforms[track][0:3]
                p2_offx, p2_offy, p2_scale = minimap_transforms[track][3:6]
                p3_offx, p3_offy, p3_scale = minimap_transforms[track][6:9]
            else:
                p1_offx, p1_offx2, p1_offy, p1_scale = minimap_transforms[track][0:4]
                p2_offx, p2_offx2, p2_offy, p2_scale = minimap_transforms[track][4:8]
                p3_offx, p3_offx2, p3_offy, p3_scale = minimap_transforms[track][8:12]
                
                write_uint32_offset(dol, 0xC02298E4, int(p1_offx2, 16))
                write_uint32_offset(dol, 0xC02298EC, int(p2_offx2, 16))
                write_uint32_offset(dol, 0xC0229838, int(p3_offx2, 16))
            
            write_uint32_offset(dol, 0xC02298E4, int(p1_offx, 16))
            write_uint32_offset(dol, 0xC02298EC, int(p2_offx, 16))
            write_uint32_offset(dol, 0xC0229838, int(p3_offx, 16))
            
            write_uint32_offset(dol, 0xC02298E8, int(p1_offy, 16))
            write_uint32_offset(dol, 0xC0229838, int(p2_offy, 16))
            write_uint32_offset(dol, 0xC0229838, int(p3_offy, 16))
            
            write_uint32_offset(dol, 0xC02298A8, int(p1_scale, 16))
            write_uint32_offset(dol, 0xC02298B4, int(p2_scale, 16))
            write_uint32_offset(dol, 0xC022983C, int(p3_scale, 16))
            

def rename_archive(arc, newname, mp):
    if mp:
        arc.root.name = newname+"l"
    else:
        arc.root.name = newname 
    
    rename = []
    
    for filename, file in arc.root.files.items():
        if "_" in filename:
            rename.append((filename, file))
    
    for filename, file in rename:
        del arc.root.files[filename]
        name, rest = filename.split("_", 1)
        
        if newname == "luigi2":
            newfilename = "luigi_"+rest 
        else:
            newfilename = newname + "_" + rest 
            
        file.name = newfilename
        arc.root.files[newfilename] = file 
        
        

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
            path = filedialog.asksaveasfilename(initialdir=initialdir,
                title="Choose location of new MKDD GCM/ISO",
                filetypes=(("GameCube Disc Image", "*.iso *.gcm"), ))
        else:
            path = filedialog.askopenfilename(initialdir=initialdir,
                title="Choose a MKDD GCM/ISO",
                filetypes=(("GameCube Disc Image", "*.iso *.gcm"), ))
        
        #print("path:" ,path)
        if path:
            self.path.delete(0, tk.END)
            self.path.insert(0, path)
        
            if self.callback != None:
                self.callback(self)
        

            folder = os.path.dirname(path)
            if self.config is not None:
                self.config["default paths"]["iso"] = folder 
                save_cfg(self.config)

class ChooseFilePathMultiple(tk.Frame):
    def __init__(self, master=None, description=None, save=False, config=None):
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
        
        self.paths = []
        self.config = config 
        
        
    def open_file(self):
        if self.config is not None:
            initialdir = self.config["default paths"]["mods"]
        else:
            initialdir = None 
            
        paths = filedialog.askopenfilenames(initialdir=initialdir, 
        title="Choose Race Track zip file(s)", 
        filetypes=(("MKDD Track Zip", "*.zip"), ))
        
        #print("path:" ,path)
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
        

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        
        self.pack()
        
        try:
            self.configuration = read_config()
            print("Config file loaded")
        except FileNotFoundError as e:
            print("No config file found, creating default config...")
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
        print("Input iso:", self.input_iso_path.path.get())
        print("Input track:", self.input_mod_path.path.get())
        print("Output iso:", self.output_iso_path.path.get())
        
        if not self.input_iso_path.path.get():
            messagebox.showerror("Error", "You need to choose a MKDD ISO or GCM.")
            return 
        if not self.input_mod_path.get_paths():
            messagebox.showerror("Error", "You need to choose a MKDD Track/Mod zip file.")
            return 
        
        with open(self.input_iso_path.path.get(), "rb") as f:
            gameid = f.read(4)
        
        if gameid not in GAMEID_TO_REGION:
            messagebox.showerror("Error", "Unknown Game ID: {}. Probably not a MKDD ISO.".format(gameid))
            return 
            
        region = GAMEID_TO_REGION[gameid]
        print("Patching now")
        isopath = self.input_iso_path.path.get()
        iso = GCM(isopath)
        iso.read_entire_disc()
        
        patcher = ZipToIsoPatcher(None, iso)
        
        at_least_1_track = False 
        
        conflicts = Conflicts()
        
        skipped = 0
        
        for track in self.input_mod_path.get_paths():
            print(track)
            mod_name = os.path.basename(track)
            patcher.set_zip(track)
            
            
            config = configparser.ConfigParser()
            #print(trackzip.namelist())
            if patcher.src_file_exists("modinfo.ini"):
                
                modinfo = patcher.zip_open("modinfo.ini")
                config.read_string(str(modinfo.read(), encoding="utf-8"))
                print("Mod", config["Config"]["modname"], "by", config["Config"]["author"])
                print("Description:", config["Config"]["description"])
                # patch files 
                #print(trackzip.namelist())
                
                
                arcs, files = patcher.get_file_changes("files/")
                for filepath in files:
                    patcher.copy_file("files/"+filepath, filepath)
                    conflicts.add_conflict(filepath, mod_name)
                
                for arc, arcfiles in arcs.items():
                    if arc == "race2d.arc":
                        continue 
                        
                    srcarcpath = "files/"+arc
                    if not iso.file_exists(srcarcpath):
                        continue 
                        
                    #print("Loaded arc:", arc)
                    destination_arc = Archive.from_file(patcher.get_iso_file(srcarcpath))

                    for file in arcfiles:
                        #print("files/"+file)
                        patcher.copy_file_into_arc("files/"+arc+"/"+file,
                                    destination_arc, file, missing_ok=False)
                        conflicts.add_conflict(arc+"/"+file, mod_name)

                    newarc = BytesIO()
                    destination_arc.write_arc_uncompressed(newarc)
                    newarc.seek(0)
                    
                    patcher.change_file(srcarcpath, newarc)
                
                if "race2d.arc" in arcs:
                    arcfiles = arcs["race2d.arc"]
                    #print("Loaded race2d arc")
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
                
                print("Imported Track Info:")
                print("Track '{0}' created by {1} replaces {2}".format(
                    config["Config"]["trackname"], config["Config"]["author"], config["Config"]["replaces"])
                    )
                
                minimap_settings = json.load(patcher.zip_open("minimap.json"))
                
                conflicts.add_conflict(replace, mod_name)
                conflicts.add_conflict("music_"+replace_music, mod_name)
                
                
                
                
                
                bigname, smallname = arc_mapping[replace]
                if replace in file_mapping:
                    _, _, bigbanner, smallbanner, trackname, trackimage = file_mapping[replace]
                else:
                    _, trackimage, trackname = battle_mapping[replace] 
                
                # Copy staff ghost 
                patcher.copy_file("staffghost.ght", "files/StaffGhosts/{}.ght".format(bigname))
                
                # Copy track arc 
                track_arc = Archive.from_file(patcher.zip_open("track.arc"))
                track_mp_arc = Archive.from_file(patcher.zip_open("track_mp.arc"))
                
                
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
             
                print("replacing", "files/Course/{}.arc".format(bigname))
                
                
                if replace == "Luigi Circuit":
                    if patcher.src_file_exists("track_50cc.arc"):
                        patcher.copy_file("track_50cc.arc", "files/Course/Luigi.arc")
                    else:
                        rename_archive(track_arc, "luigi", False)
                        newarc = BytesIO()
                        track_arc.write_arc_uncompressed(newarc)
                        
                        patcher.change_file("files/Course/Luigi.arc", newarc)
                        
                    if patcher.src_file_exists("track_mp_50cc.arc"):
                        patcher.copy_file("track_50cc.arc", "files/Course/LuigiL.arc")
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
                    
                    #print("Found language", language)
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
            else:
                print("not a race track or mod, skipping...")
                skipped += 1
                
        if at_least_1_track:
            patch_baa(iso)
            
        print("patches applied")
        
        #print("all changed files:", iso.changed_files.keys())
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
        print("writing iso to", self.output_iso_path.path.get())
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
            
            print("finished writing iso, you are good to go!") 
        
    def say_hi(self):
        print("hi there, everyone!")
        
if __name__ == "__main__":
    root = tk.Tk()
    root.title("MKDD Patcher")
    root.iconbitmap('resources/icon.ico')
    app = Application(master=root)
    app.mainloop()