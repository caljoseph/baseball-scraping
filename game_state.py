from enum import Enum, auto


class Base(Enum):
    FIRST = auto()
    SECOND = auto()
    THIRD = auto()


class Half(Enum):
    TOP = auto()
    BOTTOM = auto()


class FieldPosition(Enum):
    DESIGNATED_HITTER = "DH"
    CATCHER = "C"
    FIRST_BASE = "1B"
    SECOND_BASE = "2B"
    THIRD_BASE = "3B"
    SHORTSTOP = "SS"
    LEFT_FIELD = "LF"
    CENTER_FIELD = "CF"
    RIGHT_FIELD = "RF"


class GameState:
    __slots__ = ('home_abbr', 'away_abbr', 'inning', 'half', 'score_home', 'score_away', 'outs',
                 'bases_occupied', 'home_lineup', 'away_lineup',
                 'home_pitcher', 'home_sub_ins', 'away_pitcher', 'away_sub_ins',
                 'home_position_players', 'away_position_players', 'at_bat', 'home_has_dh', 'away_has_dh',)

    def __init__(self, home_abbr=None, away_abbr=None, inning=1, half=Half.TOP, score_home=0, score_away=0, outs=0,
                 bases_occupied=None, home_lineup=None, away_lineup=None,
                 home_pitcher=None, home_sub_ins=None, away_pitcher=None, away_sub_ins=None,
                 home_position_players=None, away_position_players=None, at_bat=1, home_has_dh=True, away_has_dh=True):
        self.home_abbr = home_abbr
        self.away_abbr = away_abbr
        self.inning = inning
        self.half = half
        self.score_home = score_home
        self.score_away = score_away
        self.outs = outs
        self.bases_occupied = bases_occupied or {
            Base.FIRST: -1,
            Base.SECOND: -1,
            Base.THIRD: -1
        }
        self.home_lineup = home_lineup or [-1] * 9  # Initialize with -1 for empty slots
        self.away_lineup = away_lineup or [-1] * 9
        self.home_pitcher = home_pitcher
        self.away_pitcher = away_pitcher
        self.home_sub_ins = home_sub_ins
        self.away_sub_ins = away_sub_ins
        self.home_position_players = home_position_players or {pos: None for pos in FieldPosition}
        self.away_position_players = away_position_players or {pos: None for pos in FieldPosition}
        self.at_bat = at_bat
        self.home_has_dh = home_has_dh
        self.away_has_dh = away_has_dh

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def set_position_player(self, team, position, player):
        if team == 'home':
            self.home_position_players[position] = player
        elif team == 'away':
            self.away_position_players[position] = player
        else:
            raise ValueError("Team must be 'home' or 'away'")

    def get_position_player(self, team, position):
        if team == 'home':
            return self.home_position_players[position]
        elif team == 'away':
            return self.away_position_players[position]
        else:
            raise ValueError("Team must be 'home' or 'away'")

    def create_decision_point(self, event, is_decision) -> dict:
        decision_point = {
            "Event_Type": event,
            "Is_Decision": is_decision,
            "Inning": self.inning,
            "Half": self.half,
            "At_Bat": self.at_bat,
            "Score_Deficit": self.score_home - self.score_away,
            "Outs": self.outs,
            "BasesOccupied": {
                "First_Base": self.bases_occupied[Base.FIRST],
                "Second_Base": self.bases_occupied[Base.SECOND],
                "Third_Base": self.bases_occupied[Base.THIRD]
            },
            "Home_Pitcher": self.home_pitcher,
            "Away_Pitcher": self.away_pitcher,
        }

        # Add individual lineup positions
        for i in range(9):
            decision_point[f"Home_Lineup_{i + 1}"] = self.home_lineup[i]
            decision_point[f"Away_Lineup_{i + 1}"] = self.away_lineup[i]

        # Add position players
        decision_point["HomePositionPlayers"] = self.home_position_players
        decision_point["AwayPositionPlayers"] = self.away_position_players

        return decision_point

    def empty_bases(self):
        self.bases_occupied = {
            Base.FIRST: -1,
            Base.SECOND: -1,
            Base.THIRD: -1
        }


