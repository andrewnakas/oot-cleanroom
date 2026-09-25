"""Item icons rendered from the game's own get-item models with our textures.

    python -m games.oot.icons <clean oot.o2r> <out dir> [--sheet sheet.png] [--only regex]

Writes <out dir>/<icon texture name>.png (32x32 RGBA). generate.py picks them up
through drawn.py (games/oot/overrides/icons). ICONS maps each icon to model
display lists, view angles and optional prim/env colours (the colours the
game's draw code would set).
"""
import os
import re
import sys

import numpy as np
from PIL import Image

from games.oot import o2r
from games.oot.dlrender import Archive, Renderer

G = "objects/object_gi_"
# icon: (display lists, yaw, pitch, roll, prim, env)
ICONS = {
    "gItemIconBombTex": ([G + "bomb_1/gGiBombDL"], 20, 10, 0),
    "gItemIconBombchuTex": ([G + "bomb_2/gGiBombchuDL"], 40, 20, 0),
    "gItemIconBoomerangTex": ([G + "boomerang/gGiBoomerangDL"], 0, 60, 0),
    "gItemIconHookshotTex": ([G + "hookshot/gGiHookshotDL"], 60, 10, -30),
    "gItemIconLongshotTex": ([G + "hookshot/gGiLongshotDL"], 60, 10, -30),
    "gItemIconBottleEmptyTex": ([G + "bottle/gGiBottleDL", G + "bottle/gGiBottleStopperDL"], 20, 10, 0),
    "gItemIconOcarinaOfTimeTex": ([G + "ocarina/gGiOcarinaTimeDL", G + "ocarina/gGiOcarinaTimeHolesDL"], 30, 30, 0),
    "gItemIconOcarinaFairyTex": ([G + "ocarina_0/gGiOcarinaFairyDL", G + "ocarina_0/gGiOcarinaFairyHolesDL"], 30, 30, 0),
    "gItemIconHammerTex": ([G + "hammer/gGiHammerDL"], 30, 10, -30),
    "gItemIconBowTex": ([G + "bow/gGiBowDL"], 0, 0, 0),
    "gItemIconSlingshotTex": ([G + "pachinko/gGiSlingshotDL"], 0, 10, 0),
    "gItemIconDekuNutTex": ([G + "nuts/gGiNutDL"], 20, 20, 0),
    "gItemIconMagicBeanTex": ([G + "bean/gGiBeanDL"], 20, 20, 0),
    "gItemIconLensOfTruthTex": ([G + "glasses/gGiLensDL", G + "glasses/gGiLensGlassDL"], 20, 10, 0),
    "gItemIconOddMushroomTex": ([G + "mushroom/gGiOddMushroomDL"], 20, 15, 0),
    "gItemIconOddPotionTex": ([G + "powder/gGiOddPotionDL"], 20, 15, 0),
    "gItemIconPocketEggTex": ([G + "egg/gGiEggMaterialDL", G + "egg/gGiEggDL"], 20, 15, 0),
    "gItemIconWeirdEggTex": ([G + "egg/gGiEggMaterialDL", G + "egg/gGiEggDL"], 20, 15, 0),
    "gItemIconEyeballFrogTex": ([G + "frog/gGiFrogDL", G + "frog/gGiFrogEyesDL"], 20, 15, 0),
    "gItemIconEyeDropsTex": ([G + "eye_lotion/gGiEyeDropsBottleDL", G + "eye_lotion/gGiEyeDropsCapDL"], 20, 10, 0),
    "gItemIconPrescriptionTex": ([G + "prescription/gGiPrescriptionDL", G + "prescription/gGiPrescriptionWritingDL"], 0, 30, 0),
    "gItemIconZeldasLetterTex": ([G + "letter/gGiLetterDL", G + "letter/gGiLetterWritingDL"], 0, 30, 0),
    "gItemIconBottleRutosLetterTex": ([G + "bottle_letter/gGiLetterBottleDL", G + "bottle_letter/gGiLetterBottleContentsDL"], 20, 10, 0),
    "gItemIconBottleMilkFullTex": ([G + "milk/gGiMilkBottleDL", G + "milk/gGiMilkBottleContentsDL"], 20, 10, 0),
    "gItemIconBottleMilkHalfTex": ([G + "milk/gGiMilkBottleDL", G + "milk/gGiMilkBottleContentsDL"], 20, 10, 0),
    "gItemIconBottleFishTex": ([G + "fish/gGiFishDL"], 60, 10, 0),
    "gItemIconBottleBugTex": ([G + "insect/gGiBugsContainerDL", G + "insect/gGiBugsGlassDL"], 20, 10, 0),
    "gItemIconBottleBlueFireTex": ([G + "fire/gGiBlueFireChamberstickDL", G + "fire/gGiBlueFireFlameDL"], 20, 10, 0),
    "gItemIconBottlePoeTex": ([G + "ghost/gGiPoeColorDL", G + "ghost/gGiGhostContainerLidDL", G + "ghost/gGiGhostContainerGlassDL", G + "ghost/gGiGhostContainerContentsDL"], 20, 10, 0),
    "gItemIconBottleBigPoeTex": ([G + "ghost/gGiBigPoeColorDL", G + "ghost/gGiGhostContainerLidDL", G + "ghost/gGiGhostContainerGlassDL", G + "ghost/gGiGhostContainerContentsDL"], 20, 10, 0),
    "gItemIconBottleFairyTex": ([G + "bottle/gGiBottleDL", G + "bottle/gGiBottleStopperDL"], 20, 10, 0),
    "gItemIconBottlePotionRedTex": ([G + "liquid/gGiRedPotColorDL", G + "liquid/gGiPotionPotDL", G + "liquid/gGiRedLiquidColorDL", G + "liquid/gGiPotionLiquidDL", G + "liquid/gGiRedPatternColorDL", G + "liquid/gGiPotionPatternDL"], 20, 10, 0),
    "gItemIconBottlePotionGreenTex": ([G + "liquid/gGiGreenPotColorDL", G + "liquid/gGiPotionPotDL", G + "liquid/gGiGreenLiquidColorDL", G + "liquid/gGiPotionLiquidDL", G + "liquid/gGiGreenPatternColorDL", G + "liquid/gGiPotionPatternDL"], 20, 10, 0),
    "gItemIconBottlePotionBlueTex": ([G + "liquid/gGiBluePotColorDL", G + "liquid/gGiPotionPotDL", G + "liquid/gGiBlueLiquidColorDL", G + "liquid/gGiPotionLiquidDL", G + "liquid/gGiBluePatternColorDL", G + "liquid/gGiPotionPatternDL"], 20, 10, 0),
    "gItemIconBootsIronTex": ([G + "boots_2/gGiIronBootsDL", G + "boots_2/gGiIronBootsRivetsDL"], 70, 10, 0),
    "gItemIconBootsHoverTex": ([G + "hoverboots/gGiHoverBootsDL"], 70, 10, 0),
    "gItemIconTunicKokiriTex": ([G + "clothes/gGiTunicDL", G + "clothes/gGiTunicCollarDL"], 0, 0, 0, (70, 180, 60, 255), (40, 110, 30, 255)),
    "gItemIconTunicGoronTex": ([G + "clothes/gGiTunicDL", G + "clothes/gGiGoronCollarColorDL", G + "clothes/gGiTunicCollarDL"], 0, 0, 0, (200, 40, 30, 255), (120, 20, 15, 255)),
    "gItemIconTunicZoraTex": ([G + "clothes/gGiTunicDL", G + "clothes/gGiZoraCollarColorDL", G + "clothes/gGiTunicCollarDL"], 0, 0, 0, (40, 70, 200, 255), (20, 35, 120, 255)),
    "gItemIconGoronsBraceletTex": ([G + "bracelet/gGiGoronBraceletDL"], 20, 50, 0),
    "gItemIconSilverGauntletsTex": ([G + "gloves/gGiSilverGauntletsColorDL", G + "gloves/gGiGauntletsDL", G + "gloves/gGiSilverGauntletsPlateColorDL", G + "gloves/gGiGauntletsPlateDL"], 20, 10, 0),
    "gItemIconGoldenGauntletsTex": ([G + "gloves/gGiGoldenGauntletsColorDL", G + "gloves/gGiGauntletsDL", G + "gloves/gGiGoldenGauntletsPlateColorDL", G + "gloves/gGiGauntletsPlateDL"], 20, 10, 0),
    "gItemIconMaskGerudoTex": ([G + "gerudomask/gGiGerudoMaskDL"], 0, 0, 0),
    "gItemIconMaskGoronTex": ([G + "golonmask/gGiGoronMaskDL"], 0, 0, 0),
    "gItemIconMaskKeatonTex": ([G + "ki_tan_mask/gGiKeatonMaskDL", G + "ki_tan_mask/gGiKeatonMaskEyesDL"], 0, 0, 0),
    "gItemIconBrokenGoronsSwordTex": ([G + "brokensword/gGiBrokenGoronSwordDL"], 90, 0, -45),
    "gItemIconSwordBiggoronTex": ([G + "longsword/gGiBiggoronSwordDL"], 90, 0, -45),
    "gItemIconBrokenGiantsKnifeTex": ([G + "brokensword/gGiBrokenGoronSwordDL"], 90, 0, -45),
    "gItemIconBombBag20Tex": ([G + "bombpouch/gGiBombBag20BagColorDL", G + "bombpouch/gGiBombBagDL", G + "bombpouch/gGiBombBag20RingColorDL", G + "bombpouch/gGiBombBagRingDL"], 20, 10, 0),
    "gItemIconBombBag30Tex": ([G + "bombpouch/gGiBombBag30BagColorDL", G + "bombpouch/gGiBombBagDL", G + "bombpouch/gGiBombBag30RingColorDL", G + "bombpouch/gGiBombBagRingDL"], 20, 10, 0),
    "gItemIconBombBag40Tex": ([G + "bombpouch/gGiBombBag40BagColorDL", G + "bombpouch/gGiBombBagDL", G + "bombpouch/gGiBombBag40RingColorDL", G + "bombpouch/gGiBombBagRingDL"], 20, 10, 0),
    "gItemIconBulletBag30Tex": ([G + "dekupouch/gGiBulletBagColorDL", G + "dekupouch/gGiBulletBagDL", G + "dekupouch/gGiBulletBagStringColorDL", G + "dekupouch/gGiBulletBagStringDL"], 20, 10, 0),
    "gItemIconBulletBag40Tex": ([G + "dekupouch/gGiBulletBagColorDL", G + "dekupouch/gGiBulletBagDL", G + "dekupouch/gGiBulletBagStringColorDL", G + "dekupouch/gGiBulletBagStringDL"], 20, 10, 0),
    "gItemIconBulletBag50Tex": ([G + "dekupouch/gGiBulletBag50ColorDL", G + "dekupouch/gGiBulletBagDL", G + "dekupouch/gGiBulletBag50StringColorDL", G + "dekupouch/gGiBulletBagStringDL"], 20, 10, 0),
    "gItemIconQuiver30Tex": ([G + "arrowcase/gGiQuiver30InnerColorDL", G + "arrowcase/gGiQuiverInnerDL", G + "arrowcase/gGiQuiver30OuterColorDL", G + "arrowcase/gGiQuiverOuterDL"], 20, 10, -20),
    "gItemIconQuiver40Tex": ([G + "arrowcase/gGiQuiver40InnerColorDL", G + "arrowcase/gGiQuiverInnerDL", G + "arrowcase/gGiQuiver40OuterColorDL", G + "arrowcase/gGiQuiverOuterDL"], 20, 10, -20),
    "gItemIconQuiver50Tex": ([G + "arrowcase/gGiQuiver50InnerColorDL", G + "arrowcase/gGiQuiverInnerDL", G + "arrowcase/gGiQuiver50OuterColorDL", G + "arrowcase/gGiQuiverOuterDL"], 20, 10, -20),
    "gItemIconDinsFireTex": ([G + "goddess/gGiMagicSpellDiamondDL", G + "goddess/gGiMagicSpellOrbDL"], 20, 10, 0, (255, 70, 20, 255), (255, 70, 20, 255)),
    "gItemIconFaroresWindTex": ([G + "goddess/gGiMagicSpellDiamondDL", G + "goddess/gGiMagicSpellOrbDL"], 20, 10, 0, (40, 220, 70, 255), (40, 220, 70, 255)),
    "gItemIconNayrusLoveTex": ([G + "goddess/gGiMagicSpellDiamondDL", G + "goddess/gGiMagicSpellOrbDL"], 20, 10, 0, (90, 140, 255, 255), (90, 140, 255, 255)),
    "gItemIconArrowFireTex": ([G + "m_arrow/gGiFireArrowColorDL", G + "m_arrow/gGiArrowMagicDL", G + "m_arrow/gGiMagicArrowDL"], 90, 0, -45),
    "gItemIconArrowIceTex": ([G + "m_arrow/gGiIceArrowColorDL", G + "m_arrow/gGiArrowMagicDL", G + "m_arrow/gGiMagicArrowDL"], 90, 0, -45),
    "gItemIconArrowLightTex": ([G + "m_arrow/gGiLightArrowColorDL", G + "m_arrow/gGiArrowMagicDL", G + "m_arrow/gGiMagicArrowDL"], 90, 0, -45),
    "gItemIconPocketCuccoTex": ([G + "niwatori/gGiChickenColorDL", G + "niwatori/gGiChickenDL", G + "niwatori/gGiChickenEyesDL"], 60, 10, 0),
    "gItemIconChickenTex": ([G + "niwatori/gGiChickenColorDL", G + "niwatori/gGiChickenDL", G + "niwatori/gGiChickenEyesDL"], 60, 10, 0),
    "gItemIconCojiroTex": ([G + "niwatori/gGiCojiroColorDL", G + "niwatori/gGiChickenDL", G + "niwatori/gGiChickenEyesDL"], 60, 10, 0),
    "gItemIconAdultsWalletTex": ([G + "purse/gGiAdultWalletColorDL", G + "purse/gGiWalletDL", G + "purse/gGiAdultWalletStringColorDL", G + "purse/gGiWalletStringDL", G + "purse/gGiAdultWalletRupeeOuterColorDL", G + "purse/gGiWalletRupeeOuterDL", G + "purse/gGiAdultWalletRupeeInnerColorDL", G + "purse/gGiWalletRupeeInnerDL"], 0, 10, 0),
    "gItemIconGiantsWalletTex": ([G + "purse/gGiGiantsWalletColorDL", G + "purse/gGiWalletDL", G + "purse/gGiGiantsWalletStringColorDL", G + "purse/gGiWalletStringDL", G + "purse/gGiGiantsWalletRupeeOuterColorDL", G + "purse/gGiWalletRupeeOuterDL", G + "purse/gGiGiantsWalletRupeeInnerColorDL", G + "purse/gGiWalletRupeeInnerDL"], 0, 10, 0),
    "gItemIconMaskBunnyHoodTex": ([G + "rabit_mask/gGiBunnyHoodDL", G + "rabit_mask/gGiBunnyHoodEyesDL"], 0, 0, 0),
    "gItemIconMaskSpookyTex": ([G + "redead_mask/gGiSpookyMaskDL"], 0, 0, 0),
    "gItemIconMaskSkullTex": ([G + "skj_mask/gGiSkullMaskDL"], 0, 0, 0),
    "gItemIconMaskTruthTex": ([G + "truth_mask/gGiMaskOfTruthDL", G + "truth_mask/gGiMaskOfTruthAccentsDL"], 0, 0, 0),
    "gItemIconMaskZoraTex": ([G + "zoramask/gGiZoraMaskDL"], 0, 0, 0),
    "gItemIconPoachersSawTex": ([G + "saw/gGiSawDL"], 0, 20, -30),
    "gItemIconScaleSilverTex": ([G + "scale/gGiSilverScaleColorDL", G + "scale/gGiScaleDL", G + "scale/gGiSilverScaleWaterColorDL", G + "scale/gGiScaleWaterDL"], 0, 0, 0),
    "gItemIconScaleGoldenTex": ([G + "scale/gGiGoldenScaleColorDL", G + "scale/gGiScaleDL", G + "scale/gGiGoldenScaleWaterColorDL", G + "scale/gGiScaleWaterDL"], 0, 0, 0),
    "gItemIconDekuSeedsTex": ([G + "seed/gGiSeedDL"], 20, 20, 0),
    "gItemIconShieldDekuTex": ([G + "shield_1/gGiDekuShieldDL"], 0, 0, 0),
    "gItemIconShieldHylianTex": ([G + "shield_2/gGiHylianShieldDL"], 0, 0, 0),
    "gItemIconShieldMirrorTex": ([G + "shield_3/gGiMirrorShieldDL", G + "shield_3/gGiMirrorShieldSymbolDL"], 0, 0, 0),
    "gItemIconSoldOutTex": ([G + "soldout/gGiSoldOutDL"], 0, 0, 0),
    "gItemIconDekuStickTex": ([G + "stick/gGiStickDL"], 90, 0, -45),
    "gItemIconSwordKokiriTex": ([G + "sword_1/gGiKokiriSwordDL"], 90, 0, -45),
    "gItemIconClaimCheckTex": ([G + "ticketstone/gGiClaimCheckDL", G + "ticketstone/gGiClaimCheckWritingDL"], 0, 20, 0),
}


# colour set by the game's draw code for models whose own DLs fix the colour:
# (rgb, "whites" = only unsaturated light pixels, "all" = recolour by luminance)
TINT = {
    "gItemIconTunicKokiriTex": ((70, 170, 60), "whites"),
    "gItemIconTunicGoronTex": ((190, 40, 30), "whites"),
    "gItemIconTunicZoraTex": ((40, 70, 190), "whites"),
    "gItemIconDinsFireTex": ((255, 90, 40), "all"),
    "gItemIconFaroresWindTex": ((60, 230, 90), "all"),
    "gItemIconNayrusLoveTex": ((110, 150, 255), "all"),
}


def tint(img, rgb, mode):
    c = np.asarray(rgb, np.float32) / 255
    lum = img[..., :3].mean(-1, keepdims=True)
    if mode == "all":
        img[..., :3] = np.clip(lum * 1.4 * c, 0, 1)
    else:
        sat = img[..., :3].max(-1) - img[..., :3].min(-1)
        m = ((sat < 0.12) & (lum[..., 0] > 0.55))[..., None]
        img[..., :3] = np.where(m, lum * c * 1.25, img[..., :3])
    return img


def outline(img, c=(0.08, 0.06, 0.04)):
    a = img[..., 3] > 0.5
    ring = np.zeros_like(a)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ring |= np.roll(np.roll(a, dy, 0), dx, 1)
    ring &= ~a
    img[ring, :3] = c
    img[ring, 3] = 1
    return img


def render_icons(arc, only=None, size=32, ss=4):
    R = Renderer(arc, size * ss)
    out = {}
    for name, spec in ICONS.items():
        if only and not re.search(only, name):
            continue
        dls = [d for d in spec[0] if d in arc.files]
        if not dls:
            continue
        yaw, pitch, roll = spec[1:4]
        prim = spec[4] if len(spec) > 4 else None
        env = spec[5] if len(spec) > 5 else None
        big = R.draw(dls, yaw, pitch, roll, prim=prim, env=env)
        small = big.reshape(size, ss, size, ss, 4).mean((1, 3))
        a = small[..., 3:4]
        small[..., :3] = np.where(a > 0, small[..., :3] / np.maximum(a, 1e-6), 0)
        small[..., 3] = (small[..., 3] > 0.45).astype(np.float32)
        if name in TINT:
            small = tint(small, *TINT[name])
        out[name] = outline(small)
    return out


def main(argv):
    src, outdir = argv[1], argv[2]
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    os.makedirs(outdir, exist_ok=True)
    arc = Archive(o2r.read_all(src))
    icons = render_icons(arc, only)
    for name, img in icons.items():
        Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGBA").save(os.path.join(outdir, name + ".png"))
    if "--sheet" in argv:
        tiles = []
        for name, img in icons.items():
            rgb = img[..., :3] * img[..., 3:4] + 0.3 * (1 - img[..., 3:4])
            tiles.append(np.kron((rgb * 255).astype(np.uint8), np.ones((4, 4, 1), np.uint8)))
        cols = 10
        while len(tiles) % cols:
            tiles.append(np.zeros_like(tiles[0]))
        rows = [np.concatenate(tiles[i:i + cols], 1) for i in range(0, len(tiles), cols)]
        Image.fromarray(np.concatenate(rows, 0)).save(argv[argv.index("--sheet") + 1])
    print(f"icons: {len(icons)} -> {outdir}")


if __name__ == "__main__":
    main(sys.argv)
