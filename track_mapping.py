# Map track name to file name in CourseName (big track banner), SceneData/coursename.arc (small track banner), 
# courseselect.arc (coname, track name) and courseselect.arc (cop, track image)
bsft = [
    "AudioRes/Stream/COURSE_BABY_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_BEACH_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_CRUISER_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_CIRCUIT_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_YCIRCUIT_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_MCIRCUIT_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_HIWAY_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_CITY_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_STADIUM_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_COLOSSEUM_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_JUNGLE_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_MOUNTAIN_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_CASTLE_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_RAINBOW_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_DESERT_0.x.32.c4.ast",
    "AudioRes/Stream/COURSE_SNOW_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_BABY_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_BEACH_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_CRUISER_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_CIRCUIT_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_YCIRCUIT_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_MCIRCUIT_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_HIWAY_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_CITY_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_STADIUM_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_COLOSSEUM_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_JUNGLE_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_MOUNTAIN_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_CASTLE_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_RAINBOW_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_DESERT_0.x.32.c4.ast",
    "AudioRes/Stream/FINALLAP_SNOW_0.x.32.c4.ast",
    "AudioRes/Stream/GOAL1_0.x.32.c4.ast",
    "AudioRes/Stream/GOAL2_0.x.32.c4.ast",
    "AudioRes/Stream/GOAL3_0.x.32.c4.ast",
    "AudioRes/Stream/BATTLE_0.x.32.c4.ast",
    "AudioRes/Stream/BATTLE2_0.x.32.c4.ast",
    "AudioRes/Stream/BATTLE3_0.x.32.c4.ast",
    "AudioRes/Stream/GOAL4_0.x.32.c4.ast",
    "AudioRes/Stream/COMMENDATION_0.x.32.c4.ast",
    "AudioRes/Stream/ENDING_0.x.32.c4.ast",
    "AudioRes/Stream/COMMENDATION2_0.x.32.c4.ast",
    "AudioRes/Stream/GOAL5_0.x.32.c4.ast",
    "AudioRes/Stream/ENDING_PAL50_0.x.32.c4.ast",
    "AudioRes/Stream/SPECIAL_0.x.32.c4.ast",
    "AudioRes/Stream/GOAL6_0.x.32.c4.ast",
    "AudioRes/Stream/GURAGURA_MARIO_0.x.32.c4.ast",
    "AudioRes/Stream/GOAL1F_0.x.32.c4.ast",
    "AudioRes/Stream/GOAL2F_0.x.32.c4.ast",
    "AudioRes/Stream/GOAL3F_0.x.32.c4.ast"
]

arc_mapping = {
    "Baby Park": ["BabyLuigi", "babyluigi"],
    "Peach Beach": ["Peach", "peach"],
    "Daisy Cruiser": ["Daisy", "daisy"],
    "Daisy Cruiser (Own Music)": ["Daisy", "daisy"],
    "Luigi Circuit 50cc": ["Luigi", "luigi"],
    "Luigi Circuit": ["Luigi2", "luigi2"],
    "Mario Circuit": ["Mario", "mario"],
    "Mario Circuit (Own Music)": ["Mario", "mario"],
    "Yoshi Circuit": ["Yoshi", "yoshi"],
    "Yoshi Circuit (Own Music)": ["Yoshi", "yoshi"],
    "Mushroom Bridge": ["Nokonoko", "nokonoko"],
    "Mushroom City": ["Patapata", "patapata"],
    "Mushroom City (Own Music)": ["Patapata", "patapata"],
    "Waluigi Stadium": ["Waluigi", "waluigi"],
    "Wario Colosseum": ["Wario", "wario"],
    "Wario Colosseum (Own Music)": ["Wario", "wario"],
    "Dino Jungle": ["Diddy", "diddy"],
    "DK Mountain": ["Donkey", "donkey"],
    "DK Mountain (Own Music)": ["Donkey", "donkey"],
    "Bowser Castle": ["Koopa", "koopa"],
    "Rainbow Road": ["Rainbow", "rainbow"],
    "Dry Dry Desert": ["Desert", "desert"],
    "Sherbet Land": ["Snow", "snow"]
}

file_mapping = {
    "Baby Park": ["COURSE_BABY_0.x.32.c4.ast", "FINALLAP_BABY_0.x.32.c4.ast",
        "BabyLuigi_name.bti", "babyluigi_names.bti", "coname_baby_park.bti", "cop_baby_park.bti"],
    "Peach Beach": ["COURSE_BEACH_0.x.32.c4.ast", "FINALLAP_BEACH_0.x.32.c4.ast",
        "Peach_name.bti", "peach_names.bti", "coname_peach_beach.bti", "cop_peach_beach.bti"],
    #"Daisy Cruiser": ["COURSE_BEACH_0.x.32.c4.ast", "FINALLAP_BEACH_0.x.32.c4.ast",
    #    "Daisy_name.bti", "daisy_names.bti", "coname_daisy_ship.bti", "cop_daisy_ship.bti"],
    "Daisy Cruiser": ["COURSE_CRUISER_0.x.32.c4.ast", "FINALLAP_CRUISER_0.x.32.c4.ast",
        "Daisy_name.bti", "daisy_names.bti", "coname_daisy_ship.bti", "cop_daisy_ship.bti"],
    "Luigi Circuit": ["COURSE_CIRCUIT_0.x.32.c4.ast", "FINALLAP_CIRCUIT_0.x.32.c4.ast",
        "Luigi_name.bti", "luigi_names.bti", "coname_luigi_circuit.bti", "cop_luigi_circuit.bti"],
    #"Mario Circuit": ["COURSE_CIRCUIT_0.x.32.c4.ast", "FINALLAP_CIRCUIT_0.x.32.c4.ast",
    #    "Mario_name.bti", "mario_names.bti", "coname_mario_circuit.bti", "cop_mario_circuit.bti"],
    "Mario Circuit": ["COURSE_MCIRCUIT_0.x.32.c4.ast", "FINALLAP_MCIRCUIT_0.x.32.c4.ast",
        "Mario_name.bti", "mario_names.bti", "coname_mario_circuit.bti", "cop_mario_circuit.bti"],
    #"Yoshi Circuit": ["COURSE_CIRCUIT_0.x.32.c4.ast", "FINALLAP_CIRCUIT_0.x.32.c4.ast",
    #    "Yoshi_name.bti", "yoshi_names.bti", "coname_yoshi_circuit.bti", "cop_yoshi_circuit.bti"],
    "Yoshi Circuit": ["COURSE_YCIRCUIT_0.x.32.c4.ast", "FINALLAP_YCIRCUIT_0.x.32.c4.ast",
        "Yoshi_name.bti", "yoshi_names.bti", "coname_yoshi_circuit.bti", "cop_yoshi_circuit.bti"],
    "Mushroom Bridge": ["COURSE_HIWAY_0.x.32.c4.ast", "FINALLAP_HIWAY_0.x.32.c4.ast",
        "Nokonoko_name.bti", "nokonoko_names.bti", "coname_kinoko_bridge.bti", "cop_kinoko_bridge.bti"
        # Nokonoko
    ],
    #"Mushroom City": ["COURSE_HIWAY_0.x.32.c4.ast", "FINALLAP_HIWAY_0.x.32.c4.ast",
    #    "Patapata_name.bti", "patapata_names.bti", "coname_kinoko_city.bti", "cop_konoko_city.bti"
    #    # Nokonoko
    #],
    "Mushroom City": ["COURSE_CITY_0.x.32.c4.ast", "FINALLAP_CITY_0.x.32.c4.ast",
        "Patapata_name.bti", "patapata_names.bti", "coname_kinoko_city.bti", "cop_konoko_city.bti"
        # Nokonoko
    ],
    "Waluigi Stadium": ["COURSE_STADIUM_0.x.32.c4.ast", "FINALLAP_STADIUM_0.x.32.c4.ast",
        "Waluigi_name.bti", "waluigi_names.bti", "coname_waluigi_stadium.bti", "cop_waluigi_stadium.bti"
    ],
    #"Wario Colosseum": ["COURSE_STADIUM_0.x.32.c4.ast", "FINALLAP_STADIUM_0.x.32.c4.ast",
    #    "Wario_name.bti", "wario_names.bti", "coname_wario_colosseum.bti", "cop_wario_colosseum.bti"
    #],
    "Wario Colosseum": ["COURSE_COLOSSEUM_0.x.32.c4.ast", "FINALLAP_COLOSSEUM_0.x.32.c4.ast",
        "Wario_name.bti", "wario_names.bti", "coname_wario_colosseum.bti", "cop_wario_colosseum.bti"
    ],
    "Dino Jungle": ["COURSE_JUNGLE_0.x.32.c4.ast", "FINALLAP_JUNGLE_0.x.32.c4.ast", 
        "Diddy_name.bti", "diddy_names.bti", "coname_dino_dino_jungle.bti", "cop_dino_dino_jungle.bti"
    ],
    #"DK Mountain": ["COURSE_JUNGLE_0.x.32.c4.ast", "FINALLAP_JUNGLE_0.x.32.c4.ast", 
    #    "Donkey_name.bti", "donkey_names.bti", "coname_dk_mountain.bti", "coname_dk_mountain.bti"
    #],
    "DK Mountain": ["COURSE_MOUNTAIN_0.x.32.c4.ast", "FINALLAP_MOUNTAIN_0.x.32.c4.ast", 
        "Donkey_name.bti", "donkey_names.bti", "coname_dk_mountain.bti", "cop_dk_mountain.bti"
    ],
    "Bowser Castle": ["COURSE_CASTLE_0.x.32.c4.ast", "FINALLAP_CASTLE_0.x.32.c4.ast",
        "Koopa_name.bti", "koopa_names.bti", "coname_bowser_castle.bti", "cop_bowser_castle.bti"
    ],
    "Rainbow Road": ["COURSE_RAINBOW_0.x.32.c4.ast", "FINALLAP_RAINBOW_0.x.32.c4.ast", 
        "Rainbow_name.bti", "rainbow_names.bti", "coname_rainbow_road.bti", "cop_rainbow_road.bti"],
    "Dry Dry Desert": ["COURSE_DESERT_0.x.32.c4.ast", "FINALLAP_DESERT_0.x.32.c4.ast", 
        "Desert_name.bti", "desert_names.bti", "coname_kara_kara_desert.bti", "cop_kara_kara_desert.bti",],
    "Sherbet Land": ["COURSE_SNOW_0.x.32.c4.ast", "FINALLAP_SNOW_0.x.32.c4.ast", 
        "Snow_name.bti", "snow_names.bti", "coname_sherbet_land.bti", "cop_sherbet_land.bti"]
}

if __name__ == "__main__":
    from os import path 
    from rarc import Archive
    
    for key, names in file_mapping.items():
        if "(Own Music)" not in key:
            lap, fastlap = names[0:2]
            print(lap)
            with open(path.join("AudioRes", "Stream", lap), "r") as f:
                pass 
            print(fastlap)
            with open(path.join("AudioRes", "Stream", fastlap), "r") as f:
                pass 
        name, names, coname, cop = names[2:6]
        
        with open(path.join("CourseName", "English", name), "r") as f:
            pass 
        
        with open(path.join("SceneData", "English", "coursename.arc"), "rb") as f:
            arc = Archive.from_file(f)
            arc["coursename"]["timg"][names]
        
        with open(path.join("SceneData", "English", "courseselect.arc"), "rb") as f:
            arc = Archive.from_file(f)
            arc["courseselect"]["timg"][coname]
            arc["courseselect"]["timg"][cop]
        
        
        print(key)
        
    for key in file_mapping:
        assert key in arc_mapping
    for key in arc_mapping:
        if "50cc" not in key:
            assert key in file_mapping