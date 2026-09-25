"""English words for text-bearing textures (the decomp's names + the game's text).

label(path) -> list of lines, or None. Lines split with "|".
"""
import re

FIX = {
    # do-action labels
    "Num1DoAction": "1", "Num2DoAction": "2", "Num3DoAction": "3", "Num4DoAction": "4",
    "Num5DoAction": "5", "Num6DoAction": "6", "Num7DoAction": "7", "Num8DoAction": "8",
    "PutAwayDoAction": "Put Away", "UnusedNaviDoAction": "Navi",
    # place title cards
    "GERudoTrainingGroundTitleCard": "Gerudo Training Ground",
    "GERudoValleyTitleCard": "Gerudo Valley", "GERudosFortressTitleCard": "Gerudo's Fortress",
    "JabuJabuTitleCard": "Inside Jabu-Jabu's Belly", "DodongosCavernTitleCard": "Dodongo's Cavern",
    "InsideGanonsCastleTitleCard": "Inside Ganon's Castle", "DekuTreeTitleCard": "Inside the Deku Tree",
    "GreatFairysFountainTitleCard": "Great Fairy's Fountain", "ChamberOfTheSagesTitleCard": "Chamber of the Sages",
    "TempleOfTimeTitleCard": "Temple of Time", "HouseOfSkulltulaTitleCard": "House of Skulltula",
    "GravekeepersHutTitleCard": "Gravekeeper's Hut", "ZorasRiverTitleCard": "Zora's River",
    "ZorasDomainTitleCard": "Zora's Domain", "ZorasFountainTitleCard": "Zora's Fountain",
    "GanonsCastleTitleCard": "Ganon's Castle", "RoyalFamilysTombTitleCard": "Royal Family's Tomb",
    "FairysFountainTitleCard": "Fairy's Fountain", "BombchuBowlingAlleyCard": "Bombchu Bowling Alley",
    "LonLonRanchTitleCard": "Lon Lon Ranch", "HappyMaskShopTitleCard": "Happy Mask Shop",
    "TreasureBoxShopTitleCard": "Treasure Box Shop", "BottomOfTheWellTitleCard": "Bottom of the Well",
    "QuestionMarkTitleCard": "???", "ThievesHideoutTitleCard": "Thieves' Hideout",
    "LakesideLaboratoryTitleCard": "Lakeside Laboratory",
    # boss title cards (name | subtitle)
    "BarinadeTitleCard": "Bio-Electric Anemone|Barinade", "VolvagiaBossTitleCard": "Subterranean Lava Dragon|Volvagia",
    "PhantomGanonTitleCard": "Evil Spirit from Beyond|Phantom Ganon", "GanondorfTitleCard": "Great King of Evil|Ganondorf",
    "GanonTitleCard": "Ganon", "GohmaTitleCard": "Parasitic Armored Arachnid|Gohma",
    "KingDodongoTitleCard": "Infernal Dinosaur|King Dodongo", "MorphaTitleCard": "Giant Aquatic Amoeba|Morpha",
    "BongoTitleCard": "Phantom Shadow Beast|Bongo Bongo", "TwinrovaTitleCard": "Sorceress Sisters|Twinrova",
    # item names
    "BiggoronsSwordItemName": "Biggoron's Sword", "BombBag20ItemName": "Bomb Bag", "BombBag30ItemName": "Big Bomb Bag",
    "BombBag40ItemName": "Biggest Bomb Bag", "BombItemName": "Bomb", "BombchuItemName": "Bombchu",
    "BottledFairyItemName": "Fairy", "BrokenGiantsKnifeItemName": "Giant's Knife (Broken)",
    "BrokenGoronsSwordItemName": "Broken Goron's Sword", "BulletBag30ItemName": "Bullet Bag",
    "BulletBag40ItemName": "Bigger Bullet Bag", "BulletBag50ItemName": "Biggest Bullet Bag",
    "DekuNutItemName": "Deku Nuts", "DekuStickItemName": "Deku Stick", "DinsFireItemName": "Din's Fire",
    "DungeonMapItemName": "Map", "EponasSongItemName": "Epona's Song", "EyeBallFrogItemName": "Eyeball Frog",
    "FaroresWindItemName": "Farore's Wind", "FireArrowItemName": "Fire Arrow", "FullMilkItemName": "Lon Lon Milk",
    "GerudosCardItemName": "Gerudo's Card", "GiantsKnifeItemName": "Giant's Knife",
    "GoldSkulltulaItemName": "Gold Skulltula Token", "GoronsBraceletItemName": "Goron's Bracelet",
    "GoronsRubyItemName": "Goron's Ruby", "HalfMilkItemName": "Lon Lon Milk (Half)",
    "IceArrowItemName": "Ice Arrow", "LensItemName": "Lens of Truth", "LightArrowItemName": "Light Arrow",
    "MaskofTruthItemName": "Mask of Truth", "MinuetOfForestItemName": "Minuet of Forest",
    "NayrusLoveItemName": "Nayru's Love", "NocturneOfShadowItemName": "Nocturne of Shadow",
    "OcarinaOfTimeItemName": "Ocarina of Time", "PieceOfHeartItemName": "Piece of Heart",
    "PreludeOfLightItemName": "Prelude of Light", "Quiver30ItemName": "Quiver",
    "Quiver40ItemName": "Big Quiver", "Quiver50ItemName": "Biggest Quiver",
    "RequiemOfSpiritItemName": "Requiem of Spirit", "RutosLetterItemName": "Ruto's Letter",
    "SOLDOUTItemName": "SOLD OUT", "SariasSongItemName": "Saria's Song",
    "SerenadeOfWaterItemName": "Serenade of Water", "SongOfStormsItemName": "Song of Storms",
    "SongOfTimeItemName": "Song of Time", "StoneofAgonyItemName": "Stone of Agony",
    "SunsSongItemName": "Sun's Song", "UnusedBigKeyItemName": "Boss Key",
    "ZeldasLetterItemName": "Zelda's Letter", "ZeldasLullabyItemName": "Zelda's Lullaby",
    "ZorasSapphireItemName": "Zora's Sapphire", "EmptyBottleItemName": "Bottle",
    "EyeDropsItemName": "Eye Drops", "PoachersSawItemName": "Poacher's Saw",
    "BoleroOfFireItemName": "Bolero of Fire", "FairyBowItemName": "Fairy Bow",
    "FairyOcarinaItemName": "Fairy Ocarina", "FairySlingshotItemName": "Fairy Slingshot",
    "GerudoMaskItemName": "Gerudo Mask", "KeatonMaskItemName": "Keaton Mask",
    # pause map names (Point = world map cursor, Position = current position)
    "DeathMountainCraterPositionName": "Death Mountain|Crater", "DeathMountainTrailPositionName": "Death Mountain|Trail",
    "GerudosFortressPointName": "Gerudo's Fortress", "GerudosFortressPositionName": "Gerudo's|Fortress",
    "HauntedWastelandPositionName": "Haunted|Wasteland", "HyliaLakesidePointName": "Lake Hylia",
    "KakarikoVillagePositionName": "Kakariko|Village", "LonLonRanchPositionName": "Lon Lon|Ranch",
    "LonLonRanchPointName": "Lon Lon Ranch", "SacredForestMeadowPositionName": "Sacred Forest|Meadow",
    "ZorasDomainPointName": "Zora's Domain", "ZorasDomainPositionName": "Zora's|Domain",
    "ZorasFountainPositionName": "Zora's|Fountain", "ZorasRiverPositionName": "Zora's|River",
    "GanonsCastlePositionName": "Ganon's|Castle", "HyruleCastlePositionName": "Hyrule|Castle",
    "DesertColossusPositionName": "Desert|Colossus", "HyruleFieldPositionName": "Hyrule|Field",
    "KokiriForestPositionName": "Kokiri|Forest", "LostWoodsPositionName": "Lost|Woods",
    "LakeHyliaPositionName": "Lake|Hylia", "GoronCityPositionName": "Goron|City",
    "GerudoValleyPositionName": "Gerudo|Valley", "QuestionMarkPositionName": "?", "QuestionMarkPointName": "?",
    # pause strings
    "PauseBotWTitle": "Bottom of the Well", "PauseDekuTitle": "Inside the Deku Tree",
    "PauseDodongoTitle": "Dodongo's Cavern", "PauseFireTitle": "Fire Temple", "PauseForestTitle": "Forest Temple",
    "PauseIceCavernTitle": "Ice Cavern", "PauseJabuTitle": "Jabu-Jabu's Belly", "PauseShadowTitle": "Shadow Temple",
    "PauseSpiritTitle": "Spirit Temple", "PauseWaterTitle": "Water Temple",
    "PauseCurrentPosition": "Current position", "PauseNo": "No", "PauseYes": "Yes",
    "PauseSaveConfirmation": "Game saved.", "PauseSavePrompt": "Would you like to save?",
    "PauseToDecide": "to Decide", "PauseToEquip": "to Equip", "PauseToEquipment": "to Equipment",
    "PauseToMap": "to Map", "PauseToPlayMelody": "to play melody", "PauseToQuestStatus": "to Quest Status",
    "PauseToSelectItem": "to Select Item", "ContinuePlaying": "Continue playing?",
    "NaviCUp": "Navi",
    # file select
    "FileSelAreYouSure2": "Are you sure ?", "FileSelAreYouSure": "Are you sure ?",
    "FileSelCheckBrightnessENGNTSC": "Adjust the brightness until|the symbol is barely visible",
    "FileSelControls": "A - Decide  •  B - Cancel", "FileSelCopyButton": "Copy",
    "FileSelCopyToWhichFile": "Copy to which file ?", "FileSelCopyWhichFile": "Copy which file ?",
    "FileSelENDButton": "END", "FileSelEraseButton": "Erase", "FileSelEraseWhichFile": "Erase which file ?",
    "FileSelFile1Button": "File 1", "FileSelFile2Button": "File 2", "FileSelFile3Button": "File 3",
    "FileSelFileCopied": "File copied.", "FileSelFileEmpty": "File empty.", "FileSelFileErased": "File erased.",
    "FileSelFileInUse": "File in use.", "FileSelHeadset": "HEADSET", "FileSelHold": "HOLD",
    "FileSelLTargeting": "L TARGETING", "FileSelMono": "MONO", "FileSelName": "Name ?",
    "FileSelNoEmptyFile": "No empty file.", "FileSelNoFileToCopy": "No file to copy.",
    "FileSelNoFileToErase": "No file to erase.", "FileSelOpenThisFile": "Open this file ?",
    "FileSelOptionsButton": "Options", "FileSelOptions": "OPTIONS", "FileSelPleaseSelectAFile": "Please select a file.",
    "FileSelQuitButton": "Quit", "FileSelSOUND": "SOUND", "FileSelSaveX": "SAVE",
    "FileSelStereo": "STEREO", "FileSelSurround": "SURROUND", "FileSelSwitch": "SWITCH",
    "FileSelYesButton": "Yes", "FileSelDISKButton": "DISK", "FileSelBackspaceButton": "←",
    # end credits / title
    "sOcarinaOfTime": "Ocarina of Time", "sPresentedBy": "presented by", "sTheEnd": "The End",
    "sTheLegendOfZelda": "The Legend of Zelda", "gTitleCopyright1998": "© 1998 Nintendo",
    "gTitleOcarinaOfTimeTMText": "OCARINA OF TIME™", "gTitleTheLegendOfText": "THE LEGEND OF",
    "gTitleDisk": "DISK",
}


def _split(name):
    s = re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    s = re.sub(r"\bOf\b", "of", s)
    s = re.sub(r"\bThe\b(?!^)", "the", s)
    return s[0].upper() + s[1:] if s else s


def key(path):
    base = path.rsplit("/", 1)[1]
    k = re.sub(r"(ENGNTSC|ENG)?Tex$", "", base)
    k = k[1:] if k.startswith("g") and k[1:2].isupper() else k
    return base, k


def label(path):
    base, k = key(path)
    if "JPN" in base:
        return None
    for cand in (k, "g" + k, base.replace("Tex", "")):
        if cand in FIX:
            return FIX[cand].split("|")
    if "ENG" not in base:
        return None
    for suf in ("DoAction", "TitleCard", "ItemName", "PositionName", "PointName"):
        if k.endswith(suf):
            return [_split(k[:-len(suf)])]
    return None
