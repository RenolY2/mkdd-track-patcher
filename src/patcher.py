import os 
import json 
import struct 
import zipfile
import pathlib
import configparser
import tkinter as tk
from io import BytesIO
from tkinter import filedialog
from tkinter import messagebox


from gcm import GCM
from dolreader import *
from readbsft import BSFT
from zip_helper import ZipToIsoPatcher
from conflict_checker import Conflicts 
from rarc import Archive, write_pad32, write_uint32
from configuration import read_config, make_default_config, save_cfg
from track_mapping import music_mapping, arc_mapping, file_mapping, bsft, battle_mapping

GAMEID_TO_REGION = {
    b"GM4E": "US",
    b"GM4P": "PAL",
    b"GM4J": "JP"
}

LANGUAGES = ["English", "Japanese", "German", "Italian", "French", "Spanish"]

VERSION = "1.0"

def copy_if_not_exist(iso, newfile, oldfile):
    """Copy a file if and only if it doesn't exist

    Args:
        iso (file): ISO gamefile
        newfile (file): New file
        oldfile (file): Old file
    """
    if not iso.file_exists("files/"+newfile):
        iso.add_new_file("files/"+newfile, iso.read_file_data("files/"+oldfile))


def patch_musicid(arc, new_music):
    """Patch music ID of arc file

    Args:
        arc (file): arc file
        new_music (str): music_mapping key name
    """

    new_id = music_mapping.get(new_music)
    if not new_id:
        return
        
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
    """Patch GCKart.baa

    Args:
        iso (file): ISO gamefile
    """
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
    """Patch minimap DOL

    Args:
        dol (file): Minimap DOL file
        track (str): Track name
        region (str): Game region (US/PAL/JP)
        minimap_setting (dict): Minimap settings
        intended_track (bool, optional): Run extra operations if False. Defaults to True.
    """
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
    """Renames arc file

    Args:
        arc (str): arc file name
        newname (str): New name to change to
        mp (bool): Whether to modify the multiplayer level or not
    """
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