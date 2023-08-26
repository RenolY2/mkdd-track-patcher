import os
import json
import struct
import sys
import textwrap
import zipfile
import pathlib
import logging
import configparser
from io import BytesIO


from .gcm import GCM
from .dolreader import *
from .readbsft import BSFT
from .zip_helper import ZipToIsoPatcher
from .conflict_checker import Conflicts
from .rarc import Archive, write_pad32, write_uint32
from .track_mapping import music_mapping, arc_mapping, file_mapping, bsft, battle_mapping
from .pybinpatch import DiffPatch, WrongSourceFile

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="> %(message)s")
log = logging.getLogger(__name__)

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


def wrap_text(text: str) -> str:
    return '\n'.join(textwrap.wrap(text))


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
    log.info("patched baa")

    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_YCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/COURSE_CIRCUIT_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_MCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/COURSE_CIRCUIT_0.x.32.c4.ast")

    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_CRUISER_0.x.32.c4.ast", "AudioRes/Stream/COURSE_BEACH_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_CITY_0.x.32.c4.ast", "AudioRes/Stream/COURSE_HIWAY_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_COLOSSEUM_0.x.32.c4.ast", "AudioRes/Stream/COURSE_STADIUM_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/COURSE_MOUNTAIN_0.x.32.c4.ast", "AudioRes/Stream/COURSE_JUNGLE_0.x.32.c4.ast")


    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_YCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_CIRCUIT_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_MCIRCUIT_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_CIRCUIT_0.x.32.c4.ast")

    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_CRUISER_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_BEACH_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_CITY_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_HIWAY_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_COLOSSEUM_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_STADIUM_0.x.32.c4.ast")
    copy_if_not_exist(iso, "AudioRes/Stream/FINALLAP_MOUNTAIN_0.x.32.c4.ast", "AudioRes/Stream/FINALLAP_JUNGLE_0.x.32.c4.ast")

    log.info("Copied ast files")


def patch_minimap_dol(dol, track, region, minimap_setting, intended_track=True):
    """Patch minimap DOL

    Args:
        dol (file): Minimap DOL file
        track (str): Track name
        region (str): Game region (US/PAL/JP)
        minimap_setting (dict): Minimap settings
        intended_track (bool, optional): Run extra operations if False. Defaults to True.
    """
    with open(str(pathlib.Path(__file__).parent.absolute()) + "/resources/minimap_locations.json", "r") as f:
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
    arc.root.name = newname+"l" if mp else newname

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


SUPPORTED_CODE_PATCHES = tuple()  # No built-in support at the moment.


def get_track_code_patches(config: configparser.ConfigParser) -> 'list[str]':
    filtered_code_patches = []
    code_patches = config["Config"].get("code_patches", '')
    for code_patch in code_patches.replace('"', '').replace("'", '').split(','):
        if code_patch := code_patch.strip().lower().replace(' ', '-'):
            filtered_code_patches.append(code_patch)
    return filtered_code_patches


def patch(
    input_iso_path: str,
    output_iso_path: str,
    custom_tracks: 'tuple[str]',
    message_callback: callable,
    prompt_callback: callable,
    error_callback: callable,
):
    log.info(f"Input iso: {input_iso_path}")
    log.info(f"Output iso: {output_iso_path}")
    log.info(f"Custom tracks: {custom_tracks}")

    # If ISO or mod zip aren't provided, raise error
    if not input_iso_path:
        error_callback("Error", "error", "You need to choose a MKDD ISO or GCM.")
        return
    if not custom_tracks:
        error_callback("Error", "error", "You need to choose a MKDD Track/Mod zip file.")
        return

    # Open iso and get first four bytes
    # Expected: GM4E / GM4P / GM4J
    with open(input_iso_path, "rb") as f:
        gameid = f.read(4)

    # Display error if not a valid gameid
    if gameid not in GAMEID_TO_REGION:
        error_callback("Error", "error",
                       "Unknown Game ID: {}. Probably not a MKDD ISO.".format(gameid))
        return

    # Get gameid
    region = GAMEID_TO_REGION[gameid]

    # Create GCM object with the ISO
    log.info("Patching now")
    iso = GCM(input_iso_path)
    iso.read_entire_disc()

    # Create ZipToIsoPatcher object
    patcher = ZipToIsoPatcher(None, iso)

    at_least_1_track = False

    conflicts = Conflicts()

    skipped = 0

    code_patches = []

    for mod in custom_tracks:
        log.info(mod)
        patcher.set_zip(mod)

        if patcher.is_code_patch():
            log.info("Found code patch")
            code_patches.append(mod)
        patcher.close()

    if len(code_patches) > 1:
        error_callback(
            "Error", "error",
            "More than one code patch selected:\n{}\nPlease only select one code patch.".format(
                "\n".join(os.path.basename(x) for x in code_patches)))

        return

    elif len(code_patches) == 1:
        patcher.set_zip(code_patches[0])
        patch_name = "codepatch_" + region + ".bin"
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
                do_continue = prompt_callback(
                    "Warning", "warning",
                    "The game executable has already been patched or is different than expected. "
                    "Patching it again may have unintended side effects (e.g. crashing) "
                    "so it is recommended to cancel patching and try again "
                    "on an unpatched, vanilla game ISO. \n\n"
                    "Do you want to continue?", ("No", "Continue"))

                if not do_continue:
                    return
                else:
                    patch.apply(src, dol, ignore_hash_mismatch=True)
                    dol.seek(0)
                    patcher.change_file("sys/main.dol", dol)
                    log.info("Applied patch, there may be side effects.")
        patcher.close()

    # Go through each mod path
    for mod in custom_tracks:
        # Get mod zip
        log.info(mod)
        mod_name = os.path.basename(mod)
        patcher.set_zip(mod)

        if patcher.is_code_patch():
            patcher.close()
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
                patcher.copy_file("files/" + filepath, "files/" + filepath)
                conflicts.add_conflict(filepath, mod_name)

            for arc, arcfiles in arcs.items():
                if arc == "race2d.arc":
                    continue

                srcarcpath = "files/" + arc
                if not iso.file_exists(srcarcpath):
                    continue

                #log.info("Loaded arc:", arc)
                destination_arc = Archive.from_file(patcher.get_iso_file(srcarcpath))

                for file in arcfiles:
                    #log.info("files/"+file)
                    try:
                        patcher.copy_file_into_arc("files/" + arc + "/" + file,
                                                   destination_arc,
                                                   file,
                                                   missing_ok=False)
                    except FileNotFoundError:
                        raise FileNotFoundError(
                            "Couldn't find '{0}' in '{1}'\n(Pay attention to arc root folder name!)"
                            .format(file, srcarcpath))

                    conflicts.add_conflict(arc + "/" + file, mod_name)

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
                    patcher.copy_file_into_arc("files/race2d.arc/" + file,
                                               race2d_arc,
                                               file,
                                               missing_ok=False)
                    conflicts.add_conflict("race2d.arc/" + file, mod_name)

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

            # Process code patches required by the custom track.
            code_patches = get_track_code_patches(config)
            unsupported_code_patches = [
                code_patch for code_patch in code_patches
                if code_patch not in SUPPORTED_CODE_PATCHES
            ]
            if unsupported_code_patches:
                unsupported_code_patches = ''.join(f'{" " * 6} • {code_patch}\n'
                                                   for code_patch in unsupported_code_patches)
                do_continue = prompt_callback(
                    "Warning", "warning",
                    f"No built-in support for code patches:\n\n{unsupported_code_patches}\n" +
                    wrap_text("These code patches are requirements for "
                              f"\"{mod_name}\". The code patches need to be applied as separate "
                              "mods, or else the custom track will not function as expected.") +
                    "\n\n"
                    "Do you want to continue?",
                    ("No", "Continue; I'll make sure patches are applied as separate mods"))

                if not do_continue:
                    return

                log.warning("Continuing without built-in support for code patches.")

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
            patch_minimap_dol(dol,
                              replace,
                              region,
                              minimap_settings,
                              intended_track=(track_arc.root.name == smallname))
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
                    courseselect_arc = Archive.from_file(
                        patcher.get_iso_file(courseselect_arc_path))

                    patcher.copy_file_into_arc(
                        "course_images/{}/track_small_logo.bti".format(srclanguage), coursename_arc,
                        "coursename/timg/{}_names.bti".format(smallname))
                    patcher.copy_file_into_arc(
                        "course_images/{}/track_name.bti".format(srclanguage), courseselect_arc,
                        "courseselect/timg/{}".format(trackname))
                    patcher.copy_file_into_arc(
                        "course_images/{}/track_image.bti".format(srclanguage), courseselect_arc,
                        "courseselect/timg/{}".format(trackimage))

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

                    patcher.copy_file_into_arc(
                        "course_images/{}/track_name.bti".format(srclanguage), mapselect_arc,
                        "mapselect/timg/{}".format(trackname))
                    patcher.copy_file_into_arc(
                        "course_images/{}/track_image.bti".format(srclanguage), mapselect_arc,
                        "mapselect/timg/{}".format(trackimage))

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
                patcher.copy_or_add_file("lap_music_normal.ast",
                                         "files/AudioRes/Stream/{}".format(normal_music),
                                         missing_ok=True)
                patcher.copy_or_add_file("lap_music_fast.ast",
                                         "files/AudioRes/Stream/{}".format(fast_music),
                                         missing_ok=True)
                if not patcher.src_file_exists("lap_music_normal.ast"):
                    patcher.copy_or_add_file("lap_music_fast.ast",
                                             "files/AudioRes/Stream/{}".format(normal_music),
                                             missing_ok=True)
                if not patcher.src_file_exists("lap_music_fast.ast"):
                    patcher.copy_or_add_file("lap_music_normal.ast",
                                             "files/AudioRes/Stream/{}".format(fast_music),
                                             missing_ok=True)
                conflicts.add_conflict("music_" + replace_music, mod_name)
        else:
            log.warning("not a race track or mod, skipping...")
            skipped += 1
        patcher.close()

    if at_least_1_track:
        patch_baa(iso)

    log.info("patches applied")

    #log.info("all changed files:", iso.changed_files.keys())
    if conflicts.conflict_appeared:
        resulting_conflicts = conflicts.get_conflicts()
        warn_text = ("File change conflicts between mods were encountered.\n"
                     "Conflicts between the following mods exist:\n\n")
        for i in range(min(len(resulting_conflicts), 5)):
            warn_text += "{0}. ".format(i + 1) + ", ".join(resulting_conflicts[i])
            warn_text += "\n"
        if len(resulting_conflicts) > 5:
            warn_text += "And {} more".format(len(resulting_conflicts) - 5)

        warn_text += ("\nIf you continue patching, the new ISO might be inconsistent. \n"
                      "Do you want to continue patching? \n")

        do_continue = prompt_callback("Warning", "warning", warn_text, ("No", "Continue"))

        if not do_continue:
            message_callback("Info", "info", "ISO patching cancelled.")
            return
    log.info(f"writing iso to {output_iso_path}")
    try:
        iso.export_disc_to_iso_with_changed_files(output_iso_path)
    except Exception as error:
        error_callback("Error while writing ISO: {0}".format(str(error)))
        raise
    else:
        if skipped == 0:
            message_callback("Info", "success", "New ISO successfully created!")
        else:
            message_callback(
                "Info", "successwarning", "New ISO successfully created!\n"
                "{0} zip file(s) skipped due to not being race tracks or mods.".format(skipped))

        log.info("finished writing iso, you are good to go!")
