"""CactusCare decision engine (Interactive CLI)."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------- Data Models

class Soil(str, Enum):
	ROCKY = "rocky"
	CLAY = "clay"
	SANDY = "sandy"
	POTTING_MIX = "potting_mix"
	UNKNOWN = "unknown"


class Container(str, Enum):
	POT = "pot"
	GROUND = "ground"


class Material(str, Enum):
	TERRACOTTA = "terracotta"
	PLASTIC = "plastic"
	OTHER = "other"
	NONE = "none"


class Drainage(str, Enum):
	GOOD = "good"
	POOR = "poor"
	UNKNOWN = "unknown"


class Light(str, Enum):
	DIRECT = "direct"
	BRIGHT_INDIRECT = "bright_indirect"
	LOW = "low"


class Action(str, Enum):
	WATER_NOW = "water_now"
	DONT_WATER = "dont_water"
	CHECK_SOIL = "check_soil"


_LIGHT_RANK = {Light.LOW: 0, Light.BRIGHT_INDIRECT: 1, Light.DIRECT: 2}


@dataclass
class Plant:
	name: str
	light_need: Light = Light.DIRECT


@dataclass
class Conditions:
	soil: Soil = Soil.UNKNOWN
	container: Container = Container.POT
	material: Material = Material.OTHER
	drainage: Drainage = Drainage.UNKNOWN
	light: Light = Light.BRIGHT_INDIRECT


@dataclass
class Weather:
	temp_c: float
	humidity_pct: float = 50
	rain_last_7d_mm: float = 0
	rain_next_3d_mm: float = 0


@dataclass
class Advice:
	action: Action
	light: str
	soil: str
	why: str


# ---------------------------------------------------------------- Logic

def _retention(c: Conditions, w: Optional[Weather]):
	score = 0
	reasons = []

	def add(points, phrase):
		nonlocal score
		score += points
		if points > 0:
			reasons.append((points, phrase))

	soil_pts = {
		Soil.CLAY: 2,
		Soil.POTTING_MIX: 1,
		Soil.UNKNOWN: 1,
		Soil.SANDY: 0,
		Soil.ROCKY: -1,
	}
	add(soil_pts[c.soil], "you're growing it in clay" if c.soil == Soil.CLAY else "the soil holds moisture")
	if c.drainage == Drainage.POOR:
		add(2, "drainage is limited")
	elif c.drainage == Drainage.UNKNOWN:
		add(1, "drainage is uncertain")
	if c.container == Container.POT:
		if c.material == Material.PLASTIC:
			add(1, "plastic pots dry slowly")
		elif c.material == Material.TERRACOTTA:
			score -= 1
	if c.light == Light.LOW:
		add(1, "low light slows drying")
	if w:
		if w.rain_last_7d_mm >= 10:
			add(2, "conditions have been wet")
		elif w.rain_last_7d_mm >= 2:
			add(1, "there was some recent rain")
		if w.humidity_pct >= 70:
			add(1, "humidity is high")
		if w.temp_c < 10:
			add(1, "it's cool, so the soil dries slowly")
		elif w.temp_c >= 32:
			score -= 1
	return score, reasons


def _water_call(c, w, score, reasons):
	if w:
		if w.temp_c < 5:
			return Action.DONT_WATER, ["it's cold and cactus can rot when cold and wet"]
		if c.container == Container.GROUND and w.rain_next_3d_mm >= 5:
			return Action.DONT_WATER, ["rain is coming in the next few days"]

	top = [p for _, p in sorted(reasons, key=lambda r: -r[0])[:3]]

	if score >= 5:
		return Action.DONT_WATER, top
	if score >= 2:
		return Action.CHECK_SOIL, top

	dry_spell = w is not None and w.rain_last_7d_mm < 2 and w.temp_c >= 10
	if dry_spell:
		return Action.WATER_NOW, ["the soil drains fast and it's been dry"]
	return Action.CHECK_SOIL, ["the soil drains fast, but I can't confirm it's dry"]


def _light_tip(plant, c):
	have, need = _LIGHT_RANK[c.light], _LIGHT_RANK[plant.light_need]
	if have < need:
		target = "direct sun" if plant.light_need == Light.DIRECT else "bright indirect light"
		return f"Move it toward {target}. It's getting less than it needs."
	if have > need:
		return "It's getting more light than it needs. Watch for scorch in hot afternoons."
	return "Light looks right. Leave it where it is."


def _soil_tip(c):
	if c.container == Container.GROUND and c.soil == Soil.CLAY:
		return "Dig in coarse sand, grit, or pumice, or plant on a raised mound."
	if c.soil == Soil.CLAY:
		return "Repot into a gritty cactus mix. Clay holds too much water."
	if c.drainage == Drainage.POOR:
		if c.container == Container.POT:
			return "Add or clear drainage holes and use a grittier mix."
		return "Improve drainage with grit or a raised bed."
	if c.soil == Soil.POTTING_MIX:
		return "Cut the mix with pumice or perlite, about half by volume."
	if c.soil == Soil.UNKNOWN or c.drainage == Drainage.UNKNOWN:
		return "Pour water through it. If it pools or takes over a minute to drain, loosen the mix."
	return "Soil looks fine for a cactus."


def _sentence(parts):
	if not parts:
		return ""
	text = ", and ".join([", ".join(parts[:-1]), parts[-1]]) if len(parts) > 1 else parts[0]
	return text[0].upper() + text[1:] + "."


def advise(plant: Plant, cond: Conditions, weather: Optional[Weather] = None) -> Advice:
    score, reasons = _retention(cond, weather)
    action, why_parts = _water_call(cond, weather, score, reasons)

    lead = {
        Action.DONT_WATER: "Don't water yet.",
        Action.CHECK_SOIL: "Check the soil before watering.",
        Action.WATER_NOW: "Water now.",
    }[action]

    why = lead + " " + _sentence(why_parts)
    if action == Action.CHECK_SOIL:
        why += " Water only if it's dry a couple of inches down."
    if weather is None:
        why += " Add your location for advice tuned to local weather."

    return Advice(action, _light_tip(plant, cond), _soil_tip(cond), why.strip())


# ---------------------------------------------------------------- Interactive CLI


def prompt_choice(options, prompt_text):

    print(f"\n{prompt_text}")
    for idx, opt in enumerate(options, 1):
        print(f" [{idx}] {opt.value}")
    while True:
        choice = input("Select number (or press Return for default [1]): ").strip()
        if not choice:
            return options[0]
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("Invalid choice, try again.")


def main():
    print("=" * 45)
    print(" 🌵 CactusCare Interactive CLI 🌵")
    print("=" * 45)

    name = input("\nWhat is your plant's name? [Default: Cactus]: ").strip() or "Cactus"

    soil = prompt_choice(list(Soil), "What type of soil is it in?")
    container = prompt_choice(list(Container), "Is it in a pot or in the ground?")

    material = Material.NONE
    if container == Container.POT:
        material = prompt_choice([m for m in Material if m != Material.NONE], "What material is the pot?")

    drainage = prompt_choice(list(Drainage), "How is the drainage?")
    light = prompt_choice(list(Light), "How much light does it get?")

    plant = Plant(name=name)
    cond = Conditions(soil=soil, container=container, material=material, drainage=drainage, light=light)

    result = advise(plant, cond)

2    print("\n" + "=" * 45)
    print(f" CARE ADVICE FOR: {name.upper()}")
    print("=" * 45)
    print(f"• Action: {result.action.value.upper()}")
    print(f"• Why: {result.why}")
    print(f"• Light Tip: {result.light}")
    print(f"• Soil Tip: {result.soil}")
    print("=" * 45 + "\n")


if __name__ == "__main__":
    main()
