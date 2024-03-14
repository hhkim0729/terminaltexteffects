"""Creates a rain effect where characters fall from the top of the terminal."""

from dataclasses import dataclass
import random
from typing import Callable

import terminaltexteffects.utils.argtypes as argtypes
from terminaltexteffects.base_character import EffectCharacter
from terminaltexteffects.utils import graphics
from terminaltexteffects.utils.geometry import Coord
from terminaltexteffects.utils.terminal import Terminal
from terminaltexteffects.utils.argsdataclass import ArgsDataClass, ArgField, argclass
from terminaltexteffects.utils import easing


def get_effect_and_args() -> tuple[any, ArgsDataClass]:
    return RainEffect, RainEffectArgs


@argclass(
    name="rain",
    formatter_class=argtypes.CustomFormatter,
    help="Rain characters from the top of the output area.",
    description="rain | Rain characters from the top of the output area.",
    epilog=f"""{argtypes.EASING_EPILOG} 
                Example: terminaltexteffects rain -a 0.01 --rain-colors 39 45 51 21""",
)
@dataclass
class RainEffectArgs(ArgsDataClass):
    rain_colors: list[str | int] = ArgField(
        cmd_name=["--rain-colors"],
        type_parser=argtypes.color,
        metavar="(XTerm [0-255] OR RGB Hex [000000-ffffff])",
        nargs="+",
        default=("00315C", "004C8F", "0075DB", "3F91D9", "78B9F2", "9AC8F5", "B8D8F8", "E3EFFC"),
        help="List of colors for the rain drops. Colors are randomly chosen from the list.",
    )

    final_color: int | str = ArgField(
        cmd_name=["--final-color"],
        type_parser=argtypes.color,
        default="ffffff",
        metavar="(XTerm [0-255] OR RGB Hex [000000-ffffff])",
        help="Color for the final character.",
    )

    movement_speed: float = ArgField(
        cmd_name="--movement-speed",
        type_parser=argtypes.float_range,
        default=(0.1, 0.2),
        metavar="(float range e.g. 0.25-0.5)",
        help="Falling speed range of the rain drops.",
    )
    
    rain_symbols: list[str]= ArgField(
        cmd_name= "--rain-symbols",
        type_parser= argtypes.symbol,
        nargs="+",
        default=("o", ".", ",", "*", "|"),
        metavar="(ASCII/UTF-8 character string)",
        help= "Space separated, unquoted, list of symbols to use for the rain drops. Symbols are randomly chosen from the list. "
    )
    
    final_gradient_stops: list[str | int] = ArgField(
        cmd_name= "--final-gradient-stops",
        type_parser= argtypes.color,
        nargs="+",
        default=("8A008A", "00D1FF", "FFFFFF"),
        metavar="(XTerm [0-255] OR RGB Hex [000000-ffffff])",
        help="Space separated, unquoted, list of colors for the character gradient (applied from bottom to top). If only one color is provided, the characters will be displayed in that color.",
    )
    
    final_gradient_steps: int= ArgField(
        cmd_name= "--final-gradient-steps",
        type_parser=argtypes.positive_int,
        nargs="+",
        default=(12),
        metavar="(int > 0)",
        help="Space separated, unquoted, list of the number of gradient steps to use. More steps will create a smoother and longer gradient animation.",
    )
        
    easing: Callable = ArgField(
        cmd_name=["--easing"],
        default=easing.in_quart,  # "IN_QUART"
        type_parser=argtypes.ease,
        help="Easing function to use for character movement.",
    )

    @classmethod
    def get_effect_class(selfClass):
        return RainEffect


class RainEffect:
    """Creates a rain effect where characters fall from the top of the output area."""

    def __init__(self, terminal: Terminal, args: RainEffectArgs):
        self.terminal = terminal
        self.args = args
        self.pending_chars: list[EffectCharacter] = []
        self.active_chars: list[EffectCharacter] = []
        self.group_by_row: dict[int, list[EffectCharacter | None]] = {}
        self.character_final_color_map: dict[EffectCharacter, graphics.Color] = {}

    def prepare_data(self) -> None:
        """Prepares the data for the effect by setting all characters y position to the input height and sorting by target y."""
        final_gradient = graphics.Gradient(self.args.final_gradient_stops, self.args.final_gradient_steps)

        for character in self.terminal.get_characters():
            self.character_final_color_map[character] = final_gradient.get_color_at_fraction(
                character.input_coord.row / self.terminal.output_area.top
            )

        for character in self.terminal.get_characters():
            raindrop_color = random.choice(self.args.rain_colors)
            rain_scn = character.animation.new_scene()
            rain_scn.add_frame(random.choice(self.args.rain_symbols), 1, color=raindrop_color)
            raindrop_gradient = graphics.Gradient([raindrop_color, self.character_final_color_map[character]], 7)
            fade_scn = character.animation.new_scene()
            fade_scn.apply_gradient_to_symbols(raindrop_gradient, character.input_symbol, 5)
            character.animation.activate_scene(rain_scn)
            character.motion.set_coordinate(Coord(character.input_coord.column, self.terminal.output_area.top))
            input_path = character.motion.new_path(
                speed=random.uniform(self.args.movement_speed[0], self.args.movement_speed[1]), ease=self.args.easing
            )
            input_path.new_waypoint(character.input_coord)

            character.event_handler.register_event(
                character.event_handler.Event.PATH_COMPLETE,
                input_path,
                character.event_handler.Action.ACTIVATE_SCENE,
                fade_scn,
            )
            character.motion.activate_path(input_path)
            self.pending_chars.append(character)
        for character in sorted(self.pending_chars, key=lambda c: c.input_coord.row):
            if character.input_coord.row not in self.group_by_row:
                self.group_by_row[character.input_coord.row] = []
            self.group_by_row[character.input_coord.row].append(character)

    def run(self) -> None:
        """Runs the effect."""
        self.prepare_data()
        self.pending_chars.clear()
        self.terminal.print()
        while self.group_by_row or self.active_chars or self.pending_chars:
            if not self.pending_chars and self.group_by_row:
                self.pending_chars.extend(self.group_by_row.pop(min(self.group_by_row.keys())))  # type: ignore
            if self.pending_chars:
                for _ in range(random.randint(1, 3)):
                    if self.pending_chars:
                        next_character = self.pending_chars.pop(random.randint(0, len(self.pending_chars) - 1))
                        self.terminal.set_character_visibility(next_character, True)
                        self.active_chars.append(next_character)

                    else:
                        break
            self.animate_chars()
            self.active_chars = [character for character in self.active_chars if character.is_active]
            self.terminal.print()

    def animate_chars(self) -> None:
        """Animates the characters by calling the tick method."""
        for character in self.active_chars:
            character.tick()
