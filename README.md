# MKDD Patcher
By Yoshi2

- New releases can be found in the **[Releases](https://github.com/RenolY2/mkdd-track-patcher/releases)** page.
- Report bugs or suggest improvements in the **[Issues](https://github.com/RenolY2/mkdd-track-patcher/issues)** page.
- Interested in MKDD modding? Check out Double Crew, a MKDD modding community: http://discord.gg/fUU36aH

The MKDD Patcher is a tool which allows users to easily import custom MKDD tracks
and other file-based mods (e.g custom drivers, or custom karts) into Mario Kart: Double Dash!!.
Patch files are specifically-created ZIP archives containing `trackinfo.ini` or `modinfo.ini`, and
all the files relating to the mod that need to be patched into the game.

Unlike difference-based patching tools like xdelta, this allows one ZIP archive to generally
work with all three main regions of MKDD (PAL, NTSC-U, NTSC-J), and multiple mods can
be patched in at once as long as the mods don't modify the same files.

# Usage
When using the Patcher, open a preferably-unmodified ISO of MKDD in the **Input ISO**.
Choose one or more MKDD mods ZIP archives that need to be patched in.
If the **Input ISO** field was empty, on choosing a MKDD ISO the **Output ISO** field
is filled in by appending `_new.iso` to the input ISO name.
Press on **Patch** to create a new ISO with the custom courses and mods patched in.

![MKDD Patcher - Screenshot](https://github.com/RenolY2/mkdd-track-patcher/assets/1853278/184d102e-c208-4db3-b087-0974e7d7fe2a)

# Folder mode
By enabling **Folder Mode**, you will be able to use patches
that aren't _zipped_, and just stored in a folder. This can allow for more rapid patch development.
When choosing mods, you will then choose the folder that contains the folders of mods.
Make sure the folder you choose doesn't contain any mod you don't want.

# How to create a custom race track or custom battle stage
If you are a modder who creates custom courses for MKDD and you want to package up your custom course
into a ZIP archive so that it is compatible with the MKDD Patcher, here is what you need to do:

The structure of the ZIP archive should be like this:
```
.
├── course_images
│   └── <Language>
│       ├── track_big_logo.bti
│       ├── track_image.bti
│       ├── track_name.bti
│       └── track_small_logo.bti
├── minimap.json
├── track.arc
├── track_mp.arc
├── track_50cc.arc
├── staffghost.ght
├── lap_music_normal.ast
├── lap_music_fast.ast
└── trackinfo.ini
```
### Legend
```
<Language> ----------- Language this is for (Described below)
track_big_logo.bti --- Track logo when starting a race
track_image.bti ------ Track background image in the cup selection screen
track_name.bti ------- Track name in the cup selection screen
track_small_logo.bti - Small track, not necessary for battle stages
minimap.json --------- This file can be exported from the MKDD Track Editor and contains position/orientation data related to the minimap
track.arc ------------ Single player track arc
track_mp.arc --------- Multi player track arc
track_50cc.arc ------- Optional, 50cc variant for Luigi Circuit
track_mp_50cc.arc ---- Optional, 50cc mp variant for Luigi Circuit
staffghost.ght ------- Optional, without it no functioning staff ghost
lap_music_normal.ast - Regular tempo music, race tracks only, not for battle stages
lap_music_fast.ast --- Fast tempo music, race tracks only, not for battle stages
```

The `trackinfo.ini` file needs to contain the following data:

    [Config]
    author = Author Name
    trackname = Custom TrackName
    replaces = Replaced TrackName
    replaces_music = Replaced Track Music Name
    main_language = Language
    code_patches = Comma-separated List


with `author` and `trackname` being the name of the author and the name of the custom course respectively.
`replaces` is the name of the course being replaced and can be one of the following:

    Baby Park
    Peach Beach
    Daisy Cruiser
    Luigi Circuit
    Mario Circuit
    Yoshi Circuit
    Mushroom Bridge
    Mushroom City
    Waluigi Stadium
    Wario Colosseum
    Dino Dino Jungle
    DK Mountain
    Bowser Castle
    Rainbow Road
    Dry Dry Desert
    Sherbet Land
    Luigi's Mansion
    Nintendo Gamecube
    Block City
    Tilt-a-Kart
    Cookie Land
    Pipe Plaza

`replaces_music` is the name of the music slot being replaced and should generally be the same as the
name of the track being replaced. Battle stages are an exception, music replacement is not supported
for them at the moment so for battle stages you can leave replaces_music as None.

`main_language` is the main language that should be used for lanuages that you didn't make bti textures for. \
Example: You set `main_language` as English and you have bti textures for English.
When somebody patches your track over the PAL game then the English textures will be used for German, French,
Italian, etc.

The following languages are supported: \
English, Japanese, German, Italian, French, Spanish

`code_patches` is an optional comma-separated list of code patches that are required by the custom
track (e.g. `type-specific-item-boxes`, `sectioned-courses`, or `cpu-only-dead-zones`). This list is
informative, and will tell the Patcher that certain code patches are required.

# How to create a custom mod
This guide is for when you want to make custom drivers, custom karts or modifications to any of the
files of MKDD, including files located inside the archive files (`.arc`). Instead of replacing `.arc` files as a whole,
only specific files inside each `.arc` can be replaced which allows for multiple mods to work at the same time
as long as they don't replace the same files.

The file structure of a mod ZIP archive should be like this:

    modinfo.ini
    files/

The modinfo file should contain the following data:

    [Config]
    author = Author Name
    modname = Mod Name
    description = Mod Description

The files folder mirrors the root file folder of MKDD. Any file you want to replace needs to be put in the files folder
at a path mirroring the file you are replacing in the game. \
Example: You would like to replace the `play1.thp` cutscene which is located at `Movie/play1.thp`. That means in the ZIP archive
the file needs to be located at `files/Movie/play1.thp` (and you need to create the Movie folder in the files folder)

Replacing files inside `.arc` files works in a similar way. You create a folder named after the arc at the correct location, inside
that folder you create a folder named after the arc's root folder name and place the file you are replacing in that
folder at a path relative to the arc's root folder. \
Example: You want to replace the model of Mario which is called driver.bmd and located inside the MRAM.arc,
at location `mram/driver/mario/driver.bmd`, with mram being the root folder name of MRAM.arc. That means you create
the chain of folders in the files folder: `files/MRAM.arc/mram/driver/mario/` and put your `driver.bmd`
at `files/MRAM.arc/mram/driver/mario/driver.bmd`.

`race2d` is an exception: Because it is an `.arc` inside an `.arc` it is handled in a special way: \
You need to create the `race2d.arc` inside the files/ folder, but otherwise you can proceed like mentioned above.
(i.e. files to be replaced in `race2d.arc` would go into `files/race2d.arc/mram_race2d/...`)


# Switching tracks to different track slots
Sometimes you might have two custom tracks that go over the same track slot. In that case, without
manual intervention, it's not possible to play both at once. In that case check the trackinfo.ini inside
one of the ZIP archives: replaces and replaces_music will need to be modified to a different track slot.
Note that some track slots in the game have hardcoded behaviour, e.g. crowd chants in Waluigi Stadium.


# Technical details
The MKDD Patcher does cool stuff to improve the custom track playing experience:
1) The transformation of driver positions into a position on the minimap is normally hardcoded but
the Patcher can patch that for every track slot and region of MKDD assuming the `minimap.json` is correct. (Should there
be a case where the patching is wrong, let me know)
2) If a custom track is moved to a different slot than it was intended for, the hardcoded minimap scaling and
offset is modified so that the minimap won't clip outside of the screen boundary or leak onto the timer or speedometer.
3) For custom race tracks, the `GCKart.baa` file is patched so that every race track in the game has a unique music track instead
of sharing the same music. (Battle stages are excluded from this, their music ID is hardcoded to play the same music unless you
assign a music ID from a race track to them in the MKDD Track Editor)


# Running from source code
- Get the source code of the Patcher from https://github.com/RenolY2/mkdd-track-patcher.
- Install Python 3 version 3.10 or newer, install the Python requirements (see `requirements.txt`), and run `mkdd_patcher.py` with it. Alternatively, execute `run.bat` if running on Windows.
