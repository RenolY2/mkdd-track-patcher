import atexit
import collections
import glob
import os
import json
import re
import shutil
import struct
import sys
import tempfile
import textwrap
import zipfile
import pathlib
import logging
import configparser
from io import BytesIO

from . import audioutils
from . import baa
from . import wsystool
from .gcm import GCM
from .dolreader import (
    DolFile,
    read_load_immediate_r0,
    read_uint32,
    write_float,
    write_load_immediate_r0,
    write_uint32_offset,
)
from .zip_helper import ZipToIsoPatcher
from .conflict_checker import Conflicts
from .rarc import Archive
from .track_mapping import music_mapping, arc_mapping, file_mapping, bsft, battle_mapping
from .pybinpatch import DiffPatch, WrongSourceFile

__version__ = '2.1.2'

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="> %(message)s")
log = logging.getLogger(__name__)

GAMEID_TO_REGION = {
    b"GM4E": "US",
    b"GM4P": "PAL",
    b"GM4J": "JP"
}

LANGUAGES = ["English", "Japanese", "German", "Italian", "French", "Spanish"]


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


def patch_audio_streams(bsft_filepath, iso):
    """
    Makes copies of the shared AST files, and writes the new BSFT file to the given destination.
    """
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

    log.info("Copied AST files")

    baa.write_bsft(bsft, bsft_filepath)

    # Although the standalone GCKart.bsft file (next to the GCKart.baa file) is not accessed in the
    # game, it will be updated too for correctness.
    with open(bsft_filepath, 'rb') as f:
        iso.changed_files["files/AudioRes/GCKart.bsft"] = BytesIO(f.read())

    log.info("Patched BSFT")


def patch_audio_waves(audio_waves_tmp_dir: str, baac_filepath: str, iso) -> dict[str, list[str]]:
    parent_dirpath = os.path.dirname(baac_filepath)

    log.info('Unpacking stock audio waves...')

    if not wsystool.check_wsystool():
        wsystool.compile_and_install_wsystool()

    NESTED_BAA_NAMES = {
        0: 'SelectVoice',
        1: 'Voice',
        2: 'CommendationVoice',
    }
    BAA_NAMES = {
        2: 'NintendoLogo',
        3: 'SoundEffects',
        4: 'BGMSamples',
    }
    ALL_BAA_NAMES = tuple(NESTED_BAA_NAMES.values()) + tuple(BAA_NAMES.values())

    retail_copy_dirpath = os.path.join(tempfile.gettempdir(), 'mkdd-retail-audio-waves')
    export_waves = not os.path.isdir(retail_copy_dirpath)

    # List of BAA names that have customizations.
    baa_names_with_customizations = set(os.listdir(audio_waves_tmp_dir))
    nested_baa_names_with_customizations = set(n for n in baa_names_with_customizations
                                               if n in NESTED_BAA_NAMES.values())

    if export_waves or nested_baa_names_with_customizations:
        # Unpack BAAC file.
        baac_content_dirpath = os.path.join(parent_dirpath, 'BAAC_CONTENT')
        baa.unpack_baac(baac_filepath, baac_content_dirpath)

        # Unpack nested BAA files.
        nested_baa_filepaths = []
        for i, baa_name in NESTED_BAA_NAMES.items():
            if not export_waves and baa_name not in baa_names_with_customizations:
                continue
            nested_baa_filename = f'{i}.baa'
            nested_baa_filepath = os.path.join(baac_content_dirpath, nested_baa_filename)
            assert os.path.isfile(nested_baa_filepath)
            nested_baa_filepaths.append(nested_baa_filepath)
            nested_baa_content_dirpath = os.path.join(baac_content_dirpath, f'{i}_BAA_CONTENT')
            baa.unpack_baa(nested_baa_filepath, nested_baa_content_dirpath)

    # Extract AW files.
    waves_content_dirpath = os.path.join(parent_dirpath, 'WAVES_CONTENT')
    os.makedirs(waves_content_dirpath)
    AW_FILENAMES = {
        'SelectVoice': 'SelectVoice_0.aw',
        'Voice': 'Voice_0.aw',
        'CommendationVoice': 'CommendationVoice_0.aw',
        'SoundEffects': 'se00_0.aw',
        'NintendoLogo': 'NintendoLogoMario_0.aw',
        'BGMSamples': 'bgm_0.aw',
    }
    for baa_name, aw_filename in AW_FILENAMES.items():
        if not export_waves and baa_name not in baa_names_with_customizations:
            continue
        aw_data = iso.read_file_data('files/AudioRes/Waves/' + aw_filename).read()
        with open(os.path.join(waves_content_dirpath, aw_filename), 'wb') as f:
            f.write(aw_data)

    # Process WSYS/AW files.
    for i, baa_name in NESTED_BAA_NAMES.items():
        if not export_waves and baa_name not in baa_names_with_customizations:
            continue
        wsys_filepath = os.path.join(baac_content_dirpath, f'{i}_BAA_CONTENT', '0.wsy')
        assert os.path.isfile(wsys_filepath)
        wsys_dirpath = os.path.join(parent_dirpath, f'WSYS_{baa_name}')
        wsystool.unpack_wsys(wsys_filepath, wsys_dirpath, waves_content_dirpath, export_waves)
    for i, baa_name in BAA_NAMES.items():
        if not export_waves and baa_name not in baa_names_with_customizations:
            continue
        wsys_filepath = os.path.join(parent_dirpath, f'{i}.wsy')
        assert os.path.isfile(wsys_filepath)
        wsys_dirpath = os.path.join(parent_dirpath, f'WSYS_{baa_name}')
        wsystool.unpack_wsys(wsys_filepath, wsys_dirpath, waves_content_dirpath, export_waves)

    if export_waves:
        # If this is the first run (i.e. the following directory does not exist), store a copy of
        # the retail audio waves in the system's temporary directory, to allow modders to peruse the
        # audio waves for follow-up customization.
        retail_copy_placeholder_dirpath = f'{retail_copy_dirpath}-placeholder'
        shutil.rmtree(retail_copy_placeholder_dirpath, ignore_errors=True)
        os.makedirs(retail_copy_placeholder_dirpath)
        for baa_name in ALL_BAA_NAMES:
            shutil.copytree(os.path.join(parent_dirpath, f'WSYS_{baa_name}'),
                            os.path.join(retail_copy_placeholder_dirpath, f'{baa_name}'))
        os.rename(retail_copy_placeholder_dirpath, retail_copy_dirpath)
    log.info(f'A copy of the retail audio waves is available in "{retail_copy_dirpath}".')

    log.info('Applying custom audio waves...')

    errors_by_file = {}

    # Apply WAV overrides.
    for baa_name in ALL_BAA_NAMES:
        src_dirpath = os.path.join(audio_waves_tmp_dir, baa_name)
        if not os.path.isdir(src_dirpath):
            continue
        wavetable_filepath = os.path.join(parent_dirpath, f'WSYS_{baa_name}', 'wavetable.json')
        with open(wavetable_filepath, 'r', encoding='utf-8') as f:
            wavetable = json.load(f)
        custom_dirpath = os.path.join(parent_dirpath, f'WSYS_{baa_name}', 'custom')
        assert os.path.isdir(custom_dirpath)
        for filename in sorted(os.listdir(src_dirpath)):
            filepath = os.path.join(src_dirpath, filename)
            wave_number = os.path.splitext(filename)[0]
            max_sample_rate = int(wavetable[wave_number]['sampleRate'])
            max_sample_count = int(wavetable[wave_number]['sampleCount'])
            errors = audioutils.conform_audio_wave(
                filepath,
                os.path.join(custom_dirpath, filename),
                max_sample_rate,
                max_sample_count,
            )
            if errors:
                errors_by_file[f'{baa_name}/{filename}'] = errors

    # Rebuild WSYS/AW files.
    for i, baa_name in NESTED_BAA_NAMES.items():
        if baa_name not in baa_names_with_customizations:
            continue
        wsys_dirpath = os.path.join(parent_dirpath, f'WSYS_{baa_name}')
        wsys_filepath = os.path.join(baac_content_dirpath, f'{i}_BAA_CONTENT', '0.wsy')
        wsystool.pack_wsys(wsys_dirpath, wsys_filepath, waves_content_dirpath)
    for i, baa_name in BAA_NAMES.items():
        if baa_name not in baa_names_with_customizations:
            continue
        wsys_dirpath = os.path.join(parent_dirpath, f'WSYS_{baa_name}')
        wsys_filepath = os.path.join(parent_dirpath, f'{i}.wsy')
        wsystool.pack_wsys(wsys_dirpath, wsys_filepath, waves_content_dirpath)

    # Inject modified AW files.
    for baa_name, aw_filename in AW_FILENAMES.items():
        if baa_name not in baa_names_with_customizations:
            continue
        with open(os.path.join(waves_content_dirpath, aw_filename), 'rb') as f:
            iso.changed_files['files/AudioRes/Waves/' + aw_filename] = BytesIO(f.read())

    if nested_baa_names_with_customizations:
        # Repack nested BAA files.
        for i, baa_name in NESTED_BAA_NAMES.items():
            if baa_name not in baa_names_with_customizations:
                continue
            nested_baa_filename = f'{i}.baa'
            nested_baa_content_dirpath = os.path.join(baac_content_dirpath, f'{i}_BAA_CONTENT')
            nested_baa_filepath = os.path.join(baac_content_dirpath, nested_baa_filename)
            baa.pack_baa(nested_baa_content_dirpath, nested_baa_filepath)

        # Repack BAAC file.
        baa.pack_baac(nested_baa_filepaths, baac_filepath)

    log.info('Custom audio waves applied.')

    return errors_by_file


def patch_minimap_dol(dol, track, region, minimap_setting, intended_track=True):
    """Patch minimap DOL

    Args:
        dol (file): Minimap DOL file
        track (str): Track name
        region (str): Game region (US/PAL/JP/US_DEBUG)
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

    if track == 'Pipe Plaza':
        # Pipe Plaza and Tilt-a-Kart happen to share the same coordinates array, difficulting the
        # use of custom battle stages in these slots if they don't have the same minimap
        # coordinates. To work around this limitation, unused floating values will be repurposed
        # for Pipe Plaza.
        corner1x, corner1z, corner2x, corner2z, orientation = addresses['Pipe Plaza (2)']

        # The four offsets to the coordinates array can be seen in a number of `lfs` instructions
        # near the `li` instruction that defines the orientation. These instructions need to be
        # tweaked to point to the unused array. The base offset is hardcoded; it's the first offset
        # seen in the `default:` case in the `switch` in `Race2D::__ct()`.
        assert region in ('US', 'PAL', 'JP', 'US_DEBUG')
        base_offset = 0x9A70 if region != 'US_DEBUG' else 0xA164
        for i, offset_from_li_instruction_address in enumerate((24, 16, 4, -4)):
            lfs_instruction_address = int(orientation, 16) + offset_from_li_instruction_address
            dol.seek(lfs_instruction_address)
            lfs_instruction = read_uint32(dol)
            lfs_instruction = (lfs_instruction & 0xFFFF0000) | (base_offset - i * 4)
            write_uint32_offset(dol, lfs_instruction, lfs_instruction_address)

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
            # The specific minimap transforms that the game applies to the replacee slot will be
            # neutralized by turning the calls to `Race2DParam::setX()`, `Race2DParam::setY()`, and
            # `Race2DParam::setS()` into no-ops.

            lfs_addresses = []

            if len(minimap_transforms[track]) == 9:
                p1_offx, p1_offy, p1_scale = minimap_transforms[track][0:3]
                p2_offx, p2_offy, p2_scale = minimap_transforms[track][3:6]
                p3_offx, p3_offy, p3_scale = minimap_transforms[track][6:9]
            else:
                # Only Peach Beach has these extra offsets.
                p1_offx, p1_offx2, p1_offy, p1_scale = minimap_transforms[track][0:4]
                p2_offx, p2_offx2, p2_offy, p2_scale = minimap_transforms[track][4:8]
                p3_offx, p3_offx2, p3_offy, p3_scale = minimap_transforms[track][8:12]

                lfs_addresses.extend([p1_offx2, p2_offx2, p3_offx2])

            lfs_addresses.extend([
                p1_offx, p2_offx, p3_offx, p1_offy, p2_offy, p3_offy, p1_scale, p2_scale, p3_scale
            ])

            lfs_addresses = [int(addr, 16) for addr in lfs_addresses]
            for lfs_address in lfs_addresses:
                bl_address = lfs_address + 4 * 2  # `bl` instruction is two instructions below.
                write_uint32_offset(dol, 0x60000000, bl_address)


CHEAT_CODE_PATTERN = re.compile(r'^([0-9a-fA-F]{8})\s*([0-9a-fA-F]{8})$')


def parse_cheat_codes(text: str,
                      dol: DolFile) -> list[tuple[int, str, int, int, int, int, int, bytes]] | str:
    cheat_codes = []

    in_string_write = False
    string_write_pending_lines = 0

    for line_index, line in enumerate(text.split('\n')):
        line_number = line_index + 1

        line = line.strip()
        if not line:
            continue

        if line[0] not in '0123456789abcdefABCEDF':
            # Skips commented lines that start with $, **, --, etc.
            continue

        matches = CHEAT_CODE_PATTERN.match(line)
        if matches is None:
            return (f'Ill-formed code at line #{line_number}:\n\n{line}\n\n'
                    'Expected layout is `________ ________` (unencrypted).')

        part1 = int(matches.group(1), base=16)
        part2 = int(matches.group(2), base=16)

        code_subtype = (part1 & 0b11000000000000000000000000000000) >> 30
        code_type = (part1 & 0b00111000000000000000000000000000) >> 27
        data_size = (part1 & 0b00000110000000000000000000000000) >> 25
        address = 0x80000000 | (part1 & 0b00000001111111111111111111111111)
        value = part2

        if not in_string_write:
            if (code_subtype, code_type) != (0, 0):
                return (f'Unsupported code type at line #{line_number}:\n\n    {line}\n\n'
                        'Only `00______ ________`, `02______ ________`, `04______ ________`, and '
                        '`06______ ________` codes are supported.')

            if data_size == 0 and value & 0xFFFFFF00 != 0:
                return (f'Unsupported 8-bit write at line #{line_number}:\n\n    {line}\n\n'
                        'The implementation of this code type differs between the Action Replay '
                        'and Gecko code handler: only single-byte writes are supported.')

            if not dol.is_address_resolvable(address):
                return (f'Unsupported code at line #{line_number}:\n\n    {line}\n\n'
                        f'Address 0x{address:08X} cannot be resolved.')

            if data_size == 0:  # 8-bit write & fill
                size = 1  # We only support single-byte writes
            elif data_size == 1:  # 16-bit write & fill
                size = ((value >> 16) + 1) * 16 // 8
            elif data_size == 2:  # 32-bit write
                size = 4
            elif data_size == 3:  # String write
                size = value

            dol.seek(address)
            if not dol.can_write_or_read_in_current_section(size):
                return (f'Unsupported code at line #{line_number}:\n\n    {line}\n\n'
                        f'Write of {size} bytes at 0x{address:08X} goes beyond the section limit.')

            cheat_codes.append((
                line_number,
                line,
                code_subtype,
                code_type,
                data_size,
                address,
                value,
                bytearray(),
            ))

            if data_size == 3:  # String write
                in_string_write = True
                string_write_pending_lines = (value + 7 if value % 8 else value) // 8
                if not string_write_pending_lines:
                    return (f'Ill-formed code at line #{line_number}:\n\n    {line}\n\n'
                            'Detected string write code with 0 lines.')
        else:
            cheat_codes[-1][7].extend(struct.pack('>II', part1, part2))
            string_write_pending_lines -= 1
            if not string_write_pending_lines:
                in_string_write = False

    if string_write_pending_lines:
        return f'Expecting {string_write_pending_lines} more lines in string write code.'

    return cheat_codes


def bake_cheat_codes(cheat_codes_filename: str, cheat_codes_by_mod: dict[str, list[tuple]],
                     dol: DolFile) -> str:
    conflicts_message = ''

    memory_map = {}
    reported = set()

    for mod_name, cheat_codes in cheat_codes_by_mod.items():
        for (line_number, line, code_subtype, code_type, data_size, address, value,
             string_payload) in cheat_codes:

            assert (code_subtype, code_type) == (0, 0)
            assert data_size in (0, 1, 2, 3)

            if data_size == 0:  # 8-bit write & fill
                # NOTE: Action Replay and Gecko treat the multiplier differently: the former uses
                # all the leftover bytes, whereas the latter uses only the first 2 bytes, leaving
                # the 3rd leftover byte unused. Therefore, it is not possible to provide unambiguous
                # support for this code type (unless all bytes are `0x00`, in which case both
                # implementations are consistent: a single write is to be written).
                assert value & 0xFFFFFF00 == 0
                multiplier = 1
                value = value & 0x000000FF
                payload = struct.pack('>B', value) * multiplier

            elif data_size == 1:  # 16-bit write & fill
                multiplier = (value >> 16) + 1
                value = value & 0x0000FFFF
                payload = struct.pack('>H', value) * multiplier

            elif data_size == 2:  # 32-bit write
                payload = struct.pack('>I', value)

            elif data_size == 3:  # String write
                assert len(string_payload) % 8 == 0
                payload = string_payload[:value]

                line += '\n...'

            dol.seek(address)
            dol.write(payload)

            # All bytes in the payload will be inserted in the memory map. If a previous cheat code
            # has inserted a different value at the address, that's a conflict that must be
            # reported.
            for i, byte in enumerate(payload):
                byte_address = address + i
                if byte_address not in memory_map:
                    memory_map[byte_address] = (byte, mod_name, line_number, line)
                    continue

                other_byte, other_mod_name, other_line_number, other_line = memory_map[byte_address]
                if other_byte == byte:
                    continue

                report_key = (mod_name, line_number, line, other_mod_name, other_line_number,
                              other_line)
                if report_key in reported:
                    continue
                reported.add(report_key)

                if conflicts_message:
                    conflicts_message += '\n\n'

                conflicts_message += (
                    f'"{other_mod_name}" ({cheat_codes_filename}) at line #{other_line_number}:'
                    f'\n'
                    f'{textwrap.indent(other_line, " " * 4)}'
                    f'\n'
                    f'"{mod_name}" ({cheat_codes_filename}) at line #{line_number}:'
                    f'\n'
                    f'{textwrap.indent(line, " " * 4)}')

    return conflicts_message


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

    # Verify that the input ISO is not a product of the MKDD Extender.
    if patcher.iso.file_exists("files/Cours0/Luigi.arc"):
        error_callback(
            "Error",
            "error",
            "The selected input ISO was generated by the MKDD Extender, and it is not supported."
            "\n\n"
            "If you wish to use the MKDD Patcher and the MKDD Extender to build an ISO, the MKDD "
            "Patcher must be used first.",
        )
        return

    # Check whether it's the debug build.
    if region == "US":
        boot = patcher.get_iso_file("sys/boot.bin")
        boot.seek(0x23)
        DEBUG_BUILD_DATE = b'2004.07.05'
        data = boot.read(len(DEBUG_BUILD_DATE))
        if data == DEBUG_BUILD_DATE:
            region = "US_DEBUG"

    at_least_1_track = False
    audio_waves_tmp_dir = None
    used_audio_waves = collections.defaultdict(list)

    cheat_codes_filename = f'cheatcodes_{region}.ini'
    cheat_codes_text_by_mod = {}

    conflicts = Conflicts()

    skipped = 0

    code_patches = []

    supported_code_patches = set(SUPPORTED_CODE_PATCHES)

    for mod in custom_tracks:
        log.info(mod)
        patcher.set_zip(mod)

        if patcher.is_code_patch():
            log.info("Found code patch")
            code_patches.append(mod)

            config = configparser.ConfigParser()
            codeinfo = patcher.zip_open("codeinfo.ini")
            config.read_string(str(codeinfo.read(), encoding="utf-8"))
            supported_code_patches |= set(get_track_code_patches(config))

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

        if patcher.src_file_exists(cheat_codes_filename):
            cheat_codes_bytes = patcher.zip_open(cheat_codes_filename).read()
            cheat_codes_text_by_mod[mod_name] = cheat_codes_bytes.decode(encoding='utf-8')

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
            add_files = config['Config'].getboolean("addfiles", fallback=False)
            # patch files
            #log.info(trackzip.namelist())

            arcs, files = patcher.get_file_changes("files/")
            for filepath in files:
                print(filepath, add_files)
                if add_files:
                    patcher.copy_or_add_file("files/" + filepath, "files/" + filepath)
                else:
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

            # Extract audio waves from ZIP file and store in temporary location.
            _, filepaths = patcher.get_file_changes('audio_waves')
            for filepath in filepaths:
                # Skip unrecognized files and directories.
                filename = os.path.basename(filepath)
                stem, ext = os.path.splitext(filename)
                if ext != '.wav':
                    log.warning('Skipped "%s": unrecognized extension; expecting `.wav`',
                                f'audio_waves/{filepath}')
                    continue
                root_dir = filepath
                while parent_dir := os.path.dirname(root_dir):
                    root_dir = parent_dir
                KNOWN_DIRECTORIES = {
                    'SelectVoice': 41,
                    'Voice': 357,
                    'CommendationVoice': 139,
                    'SoundEffects': 181,
                    'NintendoLogo': 2,
                    'BGMSamples': 121,
                }
                if root_dir not in KNOWN_DIRECTORIES:
                    log.warning('Skipped "%s": unknown root directory; known directories are: %s',
                                f'audio_waves/{filepath}', ', '.join(KNOWN_DIRECTORIES.keys()))
                    continue
                if root_dir != os.path.dirname(filepath):
                    log.warning('Skipped "%s": unrecognized nested directory',
                                f'audio_waves/{filepath}')
                    continue
                try:
                    wave_index = int(stem)
                except ValueError:
                    log.warning('Skipped "%s": unable to parse audio wave index from filename',
                                f'audio_waves/{filepath}')
                    continue
                if wave_index < 0 or KNOWN_DIRECTORIES[root_dir] <= wave_index:
                    log.warning(
                        'Skipped "%s": audio wave index `%s` is out of range; expected '
                        'range is [0, %s]',
                        f'audio_waves/{filepath}',
                        wave_index,
                        KNOWN_DIRECTORIES[root_dir] - 1,
                    )
                    continue

                corrected_filepath = os.path.join(root_dir, f'{wave_index}.wav')
                used_audio_waves[corrected_filepath.replace(os.sep, '/')].append(mod)

                data = patcher.zip_open(f'audio_waves/{filepath}').read()

                if audio_waves_tmp_dir is None:
                    audio_waves_tmp_dir = tempfile.mkdtemp(prefix='mkddpatcher_')
                    atexit.register(shutil.rmtree, audio_waves_tmp_dir, True)

                dst_filepath = os.path.join(audio_waves_tmp_dir, corrected_filepath)
                os.makedirs(os.path.dirname(dst_filepath), exist_ok=True)

                with open(dst_filepath, 'wb') as f:
                    f.write(data)

        elif patcher.src_file_exists("trackinfo.ini"):
            at_least_1_track = True
            trackinfo = patcher.zip_open("trackinfo.ini")
            config.read_string(str(trackinfo.read(), encoding="utf-8"))

            # Process code patches required by the custom track.
            code_patches = get_track_code_patches(config)
            unsupported_code_patches = [
                code_patch for code_patch in code_patches
                if code_patch not in supported_code_patches
            ]
            if unsupported_code_patches:
                unsupported_code_patches = ''.join(f'{" " * 6} • {code_patch}\n'
                                                   for code_patch in unsupported_code_patches)
                do_continue = prompt_callback(
                    "Warning", "warning",
                    f"No built-in support for code patches:\n\n{unsupported_code_patches}\n"
                    f"These code patches are requirements for \"{mod_name}\". The code patches "
                    "need to be applied as separate mods, or else the custom track will not "
                    "function as expected."
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

    # Check whether there are audio wave clashes in mods.
    audio_wave_clashes = [(filepath, mods) for filepath, mods in used_audio_waves.items()
                          if len(mods) > 1]
    if audio_wave_clashes:
        clashes_list = []
        for filepath, mods in audio_wave_clashes:
            mods_list = '\n'.join(f'     ◦ {mod}' for mod in mods)
            clashes_list.append(f'• {filepath}:\n{mods_list}')
        clashes_list = '\n\n'.join(clashes_list)

        do_continue = prompt_callback(
            "Warning", "warning",
            'The following audio waves have been encountered in multiple mods:\n\n'
            f'{clashes_list}'
            "\n\n"
            "Do you want to continue?",
            ("No", "Continue; I understand that only last mod's will be used"))

        if not do_continue:
            return

    baa_modification_required = at_least_1_track or bool(used_audio_waves)
    if baa_modification_required:
        with tempfile.TemporaryDirectory(prefix='mkddpatcher_') as tmp_dir:
            # Unpack BAA file.
            baa_filepath = os.path.join(tmp_dir, 'GCKart.baa')
            baa_content_dirpath = os.path.join(tmp_dir, 'BAA_CONTENT')
            baa_data = iso.read_file_data('files/AudioRes/GCKart.baa').read()
            with open(baa_filepath, 'wb') as f:
                f.write(baa_data)
            baa.unpack_baa(baa_filepath, baa_content_dirpath)

            if at_least_1_track:
                bsft_filenames = glob.glob('*.bsft', root_dir=baa_content_dirpath)
                assert len(bsft_filenames) == 1, 'Expecting exactly one BSFT file in `GCKart.baa`.'
                bsft_filepath = os.path.join(baa_content_dirpath, bsft_filenames[0])
                patch_audio_streams(bsft_filepath, iso)

            if used_audio_waves:
                baac_filenames = glob.glob('*.baac', root_dir=baa_content_dirpath)
                assert len(baac_filenames) == 1, 'Expecting exactly one BAAC file in `GCKart.baa`.'
                baac_filepath = os.path.join(baa_content_dirpath, baac_filenames[0])

                audio_errors_by_file = patch_audio_waves(audio_waves_tmp_dir, baac_filepath, iso)
                if audio_errors_by_file:
                    audio_errors_by_mod = collections.defaultdict(list)
                    for filepath, errors in audio_errors_by_file.items():
                        mod_name = os.path.basename(used_audio_waves[filepath][-1])
                        errors = '\n'.join(f'          ‣ {error}' for error in errors)
                        error_message = (f'     ◦ {filepath} had to be reprocessed:'
                                         '\n'
                                         f'{errors}')
                        audio_errors_by_mod[mod_name].append(error_message)

                    error_message = ''
                    for mod_name, errors in audio_errors_by_mod.items():
                        if error_message:
                            error_message += '\n\n'
                        error_message += '• ' + mod_name + '\n'
                        error_message += '\n'.join(errors)

                    do_continue = prompt_callback(
                        'Warning',
                        'warning',
                        'The following errors were encountered while processing audio waves:',
                        ('Abort', 'Continue'),
                        error_message,
                    )
                    if not do_continue:
                        return

            # Repack BAA file.
            baa.pack_baa(baa_content_dirpath, baa_filepath)
            with open(baa_filepath, 'rb') as f:
                iso.changed_files['files/AudioRes/GCKart.baa'] = BytesIO(f.read())

    if cheat_codes_text_by_mod:
        dol = DolFile(patcher.get_iso_file('sys/main.dol'))

        # Parse cheat codes.
        cheat_codes_by_mod = {}
        for mod_name, cheat_codes_text in cheat_codes_text_by_mod.items():
            cheat_codes = parse_cheat_codes(cheat_codes_text, dol)
            if isinstance(cheat_codes, str):
                error_callback(
                    'Error', 'error',
                    f'Error while parsing cheat codes in "{mod_name}" ({cheat_codes_filename}):',
                    f'{cheat_codes}')
                return
            cheat_codes_by_mod[mod_name] = cheat_codes

        # Bake cheat codes into DOL file.
        conflicts_message = bake_cheat_codes(cheat_codes_filename, cheat_codes_by_mod, dol)

        # Report whether conflicts have been encountered (i.e. two cheat codes that attempt to write
        # different values to the same memory address).
        if conflicts_message:
            do_continue = prompt_callback(
                'Warning',
                'warning',
                'The following conflicts were encountered while baking cheat codes:',
                ('Abort', 'Continue'),
                conflicts_message,
            )
            if not do_continue:
                return

        dol.get_raw_data().seek(0)
        patcher.change_file('sys/main.dol', dol.get_raw_data())

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
        error_callback("Error", "error", "Error while writing ISO: {0}".format(str(error)))
        raise
    else:
        if skipped == 0:
            message_callback("Info", "success", "New ISO successfully created!")
        else:
            message_callback(
                "Info", "successwarning", "New ISO successfully created!\n"
                "{0} zip file(s) skipped due to not being race tracks or mods.".format(skipped))

        log.info("finished writing iso, you are good to go!")
