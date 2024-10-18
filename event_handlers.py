import difflib
import re
import string
from game_state import Base, Half, FieldPosition, GameState


def update_outs(description, game_state):
    match = re.search(r'(\d+) out(?:s)?$', description)
    if match:
        outs = int(match.group(1))
        game_state.update(outs=outs)
        return outs
    return game_state.outs


def handle_out(description, game_state, player_map):
    # outs = update_outs(description, game_state)
    # we actually swallow all of these because we know the outs based on the event[out_update]
    pass
    # return f"Updated outs to {outs}. {description}"


def process_name(name):
    parts = name.split()
    if len(parts) >= 3 and all(len(part) == 2 and part.endswith('.') for part in parts[:-1]):
        name = ''.join(parts[:-1]) + ' ' + parts[-1]

    name = name.strip().rstrip(string.punctuation)

    # Replace "joshua" with "josh"
    name = name.replace("joshua", "josh").replace("Joshua", "josh")
    # Replace "luis garcia" with "luis garcia jr."
    name = name.replace("luis garcia", "luis garcia jr.").replace("Luis Garcia", "Luis Garcia Jr.")

    return remove_middle_initials(name.lower())


def get_closest_player_id(player_name, player_map):
    print(f"Attempting to get player ID for: {player_name}")

    player_name_processed = process_name(player_name)

    # Build a mapping from processed names to player IDs
    reversed_player_map = {process_name(name): player_id for player_id, name in player_map.items()}

    names_list = list(reversed_player_map.keys())

    # Use difflib to find the closest match
    matches = difflib.get_close_matches(player_name_processed, names_list, n=1, cutoff=0.6)
    if matches:
        closest_name = matches[0]
        player_id = reversed_player_map[closest_name]
        print(f"Found closest match for '{player_name}': '{closest_name}' (ID: {player_id})")
        return player_id
    else:
        print(f"Warning: No close match found for player name '{player_name}'")
        return None


def handle_stolen_base(description, game_state, player_map):
    if ':' in description:
        description = description.split(':', 1)[1].strip()
    player_name = description.split(" steals")[0].strip()

    player_id = get_closest_player_id(player_name, player_map)

    if not player_id:
        print(f"Error: Player '{player_name}' not found in player map.")
        return

    current_base = None
    for base, occupant in game_state.bases_occupied.items():
        if occupant == player_id:
            current_base = base
            break

    if not current_base:
        print(f"Error: Player '{player_name}' (ID: {player_id}) not found on any base.")
        return

    if "2nd base" in description:
        new_base = Base.SECOND
    elif "3rd base" in description:
        new_base = Base.THIRD
    elif "home" in description:
        new_base = None  # Stealing home means scoring
    else:
        print(f"Error: Unrecognized stolen base destination in description: '{description}'")
        return

    if new_base:
        game_state.bases_occupied[current_base] = -1
        game_state.bases_occupied[new_base] = player_id
        print(f"Player '{player_name}' (ID: {player_id}) successfully stole {new_base.name.lower()}.")
    else:
        game_state.bases_occupied[current_base] = -1
        print(f"Player '{player_name}' (ID: {player_id}) successfully stole home. Score updated.")


def handle_wild_pitch(description, game_state, player_map):
    abbreviations = ['Jr.', 'Sr.', 'II', 'III', 'IV', 'V']
    for abbr in abbreviations:
        description = description.replace(abbr, abbr.replace('.', '<dot>'))

    sentences = description.split('. ')
    sentences = [s.replace('<dot>', '.') for s in sentences]

    pitcher_info = sentences[0]
    base_runner_info = sentences[1:]

    for runner_info in base_runner_info:
        runner_info = runner_info.strip().rstrip('.')

        if not runner_info:
            continue

        if "scores" in runner_info:
            runner_name = runner_info.replace(" scores", "").strip()

            player_id = get_closest_player_id(runner_name, player_map)
            if not player_id:
                print(f"Error: Player '{runner_name}' not found in player map.")
                continue

            current_base = next(
                (base for base, occupant in game_state.bases_occupied.items() if occupant == player_id),
                None
            )

            if not current_base:
                print(f"Error: Player '{runner_name}' (ID: {player_id}) not found on any base.")
                continue

            game_state.bases_occupied[current_base] = -1
            print(f"Player '{runner_name}' (ID: {player_id}) scored.")

        elif " to " in runner_info:
            runner_name, base_movement = runner_info.rsplit(" to ", 1)
            runner_name = runner_name.strip()

            player_id = get_closest_player_id(runner_name, player_map)
            if not player_id:
                print(f"Error: Player '{runner_name}' not found in player map.")
                continue

            current_base = next(
                (base for base, occupant in game_state.bases_occupied.items() if occupant == player_id),
                None
            )

            if not current_base:
                print(f"Error: Player '{runner_name}' (ID: {player_id}) not found on any base.")
                continue

            if "2nd" in base_movement or "second" in base_movement:
                new_base = Base.SECOND
            elif "3rd" in base_movement or "third" in base_movement:
                new_base = Base.THIRD
            else:
                print(f"Error: Unrecognized base movement for '{runner_name}': '{base_movement}'")
                continue

            game_state.bases_occupied[current_base] = -1
            game_state.bases_occupied[new_base] = player_id
            print(f"Player '{runner_name}' (ID: {player_id}) moved to {new_base.name.lower()}.")


def handle_passed_ball(description, game_state, player_map):
    parts = description.split(". ")
    catcher_info = parts[0]
    base_runner_info = parts[1:]

    runner_movements = []
    for runner_info in base_runner_info:
        runner_info = runner_info.strip()
        if "scores" in runner_info:
            runner_name = runner_info.replace(" scores", "").strip()
            runner_movements.append((runner_name, "scores"))
        elif " to " in runner_info:
            runner_name, base_movement = runner_info.split(" to ")
            runner_name = runner_name.strip()
            runner_movements.append((runner_name, base_movement.strip()))

    runner_movements.sort(key=lambda x: (
        0 if x[1] == "scores" else
        1 if "3rd" in x[1] else
        2 if "2nd" in x[1] else 3
    ))

    for runner_name, movement in runner_movements:
        player_id = get_closest_player_id(runner_name, player_map)
        if not player_id:
            print(f"Error: Player '{runner_name}' not found in player map.")
            continue

        current_base = None
        for base, occupant in game_state.bases_occupied.items():
            if occupant == player_id:
                current_base = base
                break

        if not current_base:
            print(f"Error: Player '{runner_name}' (ID: {player_id}) not found on any base.")
            continue

        if movement == "scores":
            game_state.bases_occupied[current_base] = -1
            print(f"Player '{runner_name}' (ID: {player_id}) scored.")
        else:
            if "3rd" in movement:
                new_base = Base.THIRD
            elif "2nd" in movement:
                new_base = Base.SECOND
            else:
                print(f"Error: Unrecognized base movement for '{runner_name}': '{movement}'")
                continue

            game_state.bases_occupied[current_base] = -1
            game_state.bases_occupied[new_base] = player_id
            print(f"Player '{runner_name}' (ID: {player_id}) moved to {new_base.name.lower()}.")


def handle_balk(description, game_state, player_map):
    if "on a balk" not in description:
        print("Error: Not a valid balk event description.")
        return

    if "batting," in description:
        parts = description.split("batting, ")[1]
    else:
        print("Error: Malformed balk description.")
        return

    base_runner_info = parts.split(" on a balk. ")

    for runner_info in base_runner_info:
        runner_info = runner_info.strip()

        if "advances to" in runner_info:
            runner_name, base_movement = runner_info.split(" advances to ")
            runner_name = runner_name.strip()

            player_id = get_closest_player_id(runner_name, player_map)
            if not player_id:
                print(f"Error: Player '{runner_name}' not found in player map.")
                continue

            current_base = None
            for base, occupant in game_state.bases_occupied.items():
                if occupant == player_id:
                    current_base = base
                    break

            if not current_base:
                print(f"Error: Player '{runner_name}' (ID: {player_id}) not found on any base.")
                continue

            if "2nd" in base_movement:
                new_base = Base.SECOND
            elif "3rd" in base_movement:
                new_base = Base.THIRD
            elif "scores" in base_movement:
                new_base = None
            else:
                print(f"Error: Unrecognized base movement for '{runner_name}': '{base_movement}'")
                continue

            if new_base:
                game_state.bases_occupied[current_base] = -1
                game_state.bases_occupied[new_base] = player_id
                print(f"Player '{runner_name}' (ID: {player_id}) moved to {new_base.name.lower()}.")
            else:
                game_state.bases_occupied[current_base] = -1
                print(f"Player '{runner_name}' (ID: {player_id}) scored.")


def handle_offensive_sub(description, game_state, player_map):
    match = re.search(r'(?:runner|hitter)\s+(.+?)\s+replaces\s+(.+?)$', description, re.IGNORECASE)
    if not match:
        print(f"Error: Could not parse player names from description: {description}")
        return

    new_player_name = process_name(match.group(1).strip())
    old_player_name = process_name(match.group(2).strip())

    new_player_id = get_closest_player_id(new_player_name, player_map)
    old_player_id = get_closest_player_id(old_player_name, player_map)

    if not new_player_id or not old_player_id:
        print(
            f"Warning: Could not find one or both players in the player map: '{new_player_name}', '{old_player_name}'")
        return

    team = 'away' if game_state.half == Half.TOP else 'home'

    if team == 'away':
        if(game_state.away_pitcher == old_player_id):
            game_state.away_pitcher = None
            print("found an offensive sub where the person being subbed out is the pitcher")
    else:
        if game_state.home_pitcher == old_player_id:
            game_state.home_pitcher = None
            print("found an offensive sub where the person being subbed out is the pitcher")


    _replace_in_batting_order(game_state, team, old_player_id, new_player_id)

    current_dh = game_state.get_position_player(team, FieldPosition.DESIGNATED_HITTER)
    if old_player_id != current_dh:
        _replace_position_player(game_state, team, old_player_id, None)
    else:
        _replace_position_player(game_state, team, old_player_id, new_player_id)

    if "Pinch-runner" in description:
        _replace_on_base(game_state, old_player_id, new_player_id)
        print(
            f"Pinch-runner: {new_player_name} (ID: {new_player_id}) replaces {old_player_name} (ID: {old_player_id}) on the base paths.")
    else:
        print(
            f"Pinch-hitter: {new_player_name} (ID: {new_player_id}) replaces {old_player_name} (ID: {old_player_id}) in the batting order.")


def handle_defensive_sub(description, game_state, player_map):
    new_player_name, old_player_name = _extract_players_from_def_sub_desc(description)
    new_player_id = get_closest_player_id(new_player_name, player_map)
    old_player_id = get_closest_player_id(old_player_name, player_map)

    team = 'home' if game_state.half == Half.TOP else 'away'

    if new_player_id and old_player_id:
        print(
            f"Defensive substitution: {new_player_name} (ID: {new_player_id}) replaces {old_player_name} (ID: {old_player_id}).")
        _replace_in_batting_order(game_state, team, old_player_id, new_player_id)
        _replace_position_player(game_state, team, old_player_id, new_player_id)
    else:
        if not new_player_id:
            print(f"Warning: Unable to find new player '{new_player_name}' in player map.")
        if not old_player_id:
            print(f"Warning: Unable to find old player '{old_player_name}' in player map.")


def handle_defensive_switch(description, game_state, player_map):
    # Determine the format of the description and extract relevant details
    if "remains in the game as" in description:
        # Format: "player_name remains in the game as the new_position"
        player_name_part = description.split("remains in the game as")[0].strip()
        to_position_name = description.split("remains in the game as the ")[1].strip().lower()
        from_position = None  # No specified from_position in this case
    else:
        # Format: "switch from old_position to new_position for player_name"
        from_position_name = description.split("switch from ")[1].split(" to ")[0].strip().lower()
        to_position_name = description.split(" to ")[1].split(" for ")[0].strip().lower()
        player_name_part = description.split("for")[1].strip()
        from_position = _map_position_name_to_enum(from_position_name)

    # Clean the player's name and get the player ID
    player_name = process_name(player_name_part)
    player_id = get_closest_player_id(player_name, player_map)

    if not player_id:
        print(f"Warning: Player '{player_name}' not found in the player map.")
        return

    # Determine the team based on the game state
    team = 'home' if game_state.half == Half.TOP else 'away'

    # Map the to_position name to the corresponding FieldPosition enum
    to_position = _map_position_name_to_enum(to_position_name)
    if to_position is None:
        print(f"Warning: Could not map '{to_position_name}' to a valid field position.")
        return

    # Update the defensive positions in the game state using set_position_player method
    if from_position:
        current_player_in_from_position = game_state.get_position_player(team, from_position)
        if current_player_in_from_position == player_id:
            # Clear the from position if the player is indeed occupying it
            game_state.set_position_player(team, from_position, None)

    # Move the player to the new position
    game_state.set_position_player(team, to_position, player_id)

    # If the player was the DH and is moving to a defensive position, set DH to None
    current_dh = game_state.get_position_player(team, FieldPosition.DESIGNATED_HITTER)
    current_pitcher = game_state.home_pitcher if team == 'home' else game_state.away_pitcher

    if current_dh == player_id:
        # The player was the DH, check if they are also the pitcher (Shohei Ohtani case)
        if player_id != current_pitcher:
            # The player was the DH and is now playing a defensive position other than pitcher
            # The DH role is forfeited for the rest of the game
            game_state.set_position_player(team, FieldPosition.DESIGNATED_HITTER, None)
            if team == 'home':
                game_state.home_has_dh = False
            else:
                game_state.away_has_dh = False

def handle_pitching_sub(description, game_state, player_map):
    if "enters the batting order" in description:
        parts = description.split()
        new_player_name = process_name(' '.join(parts[1:3]))
        old_player_name = process_name(' '.join(parts[-5:-3]))
        batting_position = parts[parts.index("batting") + 1].rstrip(',')

        new_player_id = get_closest_player_id(new_player_name, player_map)
        old_player_id = get_closest_player_id(old_player_name, player_map)

        if not new_player_id or not old_player_id:
            return

        team = 'home' if game_state.half == Half.TOP else 'away'
        _replace_in_batting_order(game_state, team, old_player_id, new_player_id)
        return

    match = re.match(r"Pitching Change:\s*(.+?)\s+replaces\s+(.+?)(?:,\s*batting.*)?\.?$", description)
    if not match:
        return

    new_pitcher_name = process_name(match.group(1))
    old_pitcher_name = process_name(match.group(2))

    new_pitcher_id = get_closest_player_id(new_pitcher_name, player_map)
    old_pitcher_id = get_closest_player_id(old_pitcher_name, player_map)

    if not new_pitcher_id or not old_pitcher_id:
        return

    team = 'home' if game_state.half == Half.TOP else 'away'
    _replace_position_player(game_state, team, old_pitcher_id, new_pitcher_id)

    # If the DH has been forfeited, update the batting order
    has_dh = game_state.home_has_dh if team == 'home' else game_state.away_has_dh
    if not has_dh:
        # If there's no DH, the pitcher is in the batting order
        _replace_in_batting_order(game_state, team, old_pitcher_id, new_pitcher_id)


def _map_position_name_to_enum(position_name):
    # Clean the position name by removing any periods and extra whitespace
    cleaned_position_name = position_name.replace('.', '').strip().lower()

    # Map cleaned position names to the FieldPosition enum
    position_mapping = {
        "catcher": FieldPosition.CATCHER,
        "first baseman": FieldPosition.FIRST_BASE,
        "first base": FieldPosition.FIRST_BASE,
        "second baseman": FieldPosition.SECOND_BASE,
        "second base": FieldPosition.SECOND_BASE,
        "third baseman": FieldPosition.THIRD_BASE,
        "third base": FieldPosition.THIRD_BASE,
        "shortstop": FieldPosition.SHORTSTOP,
        "left fielder": FieldPosition.LEFT_FIELD,
        "left field": FieldPosition.LEFT_FIELD,
        "center fielder": FieldPosition.CENTER_FIELD,
        "center field": FieldPosition.CENTER_FIELD,
        "right fielder": FieldPosition.RIGHT_FIELD,
        "right field": FieldPosition.RIGHT_FIELD,
        "pitcher": None,  # Pitcher is handled separately in the logic
        "designated hitter": FieldPosition.DESIGNATED_HITTER
    }
    return position_mapping.get(cleaned_position_name)


def handle_pickoff_error_1b(description, game_state, player_map):
    print("Handling Pickoff Error at 1B")
    scored_players = []

    if "scores" in description:
        for player_name in player_map.values():
            if process_name(player_name) in description.lower():
                player_id = get_closest_player_id(player_name, player_map)
                if not player_id:
                    print(f"Warning: Player '{player_name}' not found in player map.")
                    continue
                for base, occupant in game_state.bases_occupied.items():
                    if occupant == player_id:
                        game_state.bases_occupied[base] = -1
                        scored_players.append(player_id)
                        print(f"Player '{player_name}' (ID: {player_id}) scored.")
                        break

    runner_on_first = game_state.bases_occupied.get(Base.FIRST, -1)
    runner_on_second = game_state.bases_occupied.get(Base.SECOND, -1)

    if runner_on_first != -1 and runner_on_first not in scored_players:
        game_state.bases_occupied[Base.FIRST] = -1
        game_state.bases_occupied[Base.SECOND] = runner_on_first
        print(f"Runner on 1st (Player ID: {runner_on_first}) advanced to 2nd.")

    if runner_on_second != -1 and runner_on_second not in scored_players:
        game_state.bases_occupied[Base.SECOND] = -1
        game_state.bases_occupied[Base.THIRD] = runner_on_second
        print(f"Runner on 2nd (Player ID: {runner_on_second}) advanced to 3rd.")


def handle_pickoff_error_2b(description, game_state, player_map):
    print("Handling Pickoff Error at 2B")
    scored_players = []

    if "scores" in description:
        for player_name in player_map.values():
            if process_name(player_name) in description.lower():
                player_id = get_closest_player_id(player_name, player_map)
                if not player_id:
                    print(f"Warning: Player '{player_name}' not found in player map.")
                    continue
                for base, occupant in game_state.bases_occupied.items():
                    if occupant == player_id:
                        game_state.bases_occupied[base] = -1
                        scored_players.append(player_id)
                        print(f"Player '{player_name}' (ID: {player_id}) scored.")
                        break

    runner_on_second = game_state.bases_occupied.get(Base.SECOND, -1)
    runner_on_first = game_state.bases_occupied.get(Base.FIRST, -1)

    if runner_on_second != -1 and runner_on_second not in scored_players:
        game_state.bases_occupied[Base.SECOND] = -1
        game_state.bases_occupied[Base.THIRD] = runner_on_second
        print(f"Runner on 2nd (Player ID: {runner_on_second}) advanced to 3rd.")

    if runner_on_first != -1 and runner_on_first not in scored_players:
        game_state.bases_occupied[Base.FIRST] = -1
        game_state.bases_occupied[Base.SECOND] = runner_on_first
        print(f"Runner on 1st (Player ID: {runner_on_first}) advanced to 2nd.")


def handle_pickoff_error_3b(description, game_state, player_map):
    print("Handling Pickoff Error at 3B")
    scored_players = []

    if "scores" in description:
        for player_name in player_map.values():
            if process_name(player_name) in description.lower():
                player_id = get_closest_player_id(player_name, player_map)
                if not player_id:
                    print(f"Warning: Player '{player_name}' not found in player map.")
                    continue
                for base, occupant in game_state.bases_occupied.items():
                    if occupant == player_id:
                        game_state.bases_occupied[base] = -1
                        scored_players.append(player_id)
                        print(f"Player '{player_name}' (ID: {player_id}) scored.")
                        break

    # No further base advancements as the pickoff error occurred at 3B
    # and any runners on bases would have been handled above


def _extract_players_from_def_sub_desc(description):
    # Remove 'Defensive Substitution:' from the start
    description = description.replace('Defensive Substitution:', '').strip()

    # Split the description into parts
    parts = description.split(',')

    # Extract new player name (always comes first)
    new_player_name = parts[0].strip().split(' replaces ')[0].strip()

    # Find the old player name
    old_player_pattern = r'replaces\s+(.*?)(?:,|\s*$)'
    old_player_match = re.search(old_player_pattern, description)
    old_player_name = old_player_match.group(1) if old_player_match else None

    # Clean up player names
    if old_player_name:
        # Remove position if it's included with the old player's name
        old_player_name = re.sub(
            r'\b(first baseman|second baseman|shortstop|third baseman|left fielder|right fielder|catcher|center fielder|pitcher)\s+',
            '', old_player_name)
        old_player_name = old_player_name.strip()

    old_player_name = remove_middle_initials(old_player_name)
    new_player_name = remove_middle_initials(new_player_name)

    return new_player_name, old_player_name



def _replace_on_base(game_state, old_player_id, new_player_id):
    for base, occupant in game_state.bases_occupied.items():
        if occupant == old_player_id:
            game_state.bases_occupied[base] = new_player_id
            print(f"Player {new_player_id} replaces {old_player_id} on {base.name}.")
            return
    print(f"Warning: Could not find {old_player_id} on any base to replace.")


def _replace_position_player(game_state, team, old_player_id, new_player_id):
    print("entered replace position player/pitcher function: ")
    print(" team: ", team)
    print(" old_player_id: ", old_player_id)
    print(" new_player_id: ", new_player_id)

    # Determine which team's position players and flags we are working with
    if team == 'home':
        position_players = game_state.home_position_players
        current_pitcher = game_state.home_pitcher
    elif team == 'away':
        position_players = game_state.away_position_players
        current_pitcher = game_state.away_pitcher
    else:
        raise ValueError("Team must be 'home' or 'away'")

    print(" current_pitcher: ", current_pitcher)

    # Replace a position player in the field
    for position, player_id in position_players.items():
        if player_id == old_player_id:
            print(f"Replacing {old_player_id} at {position} with {new_player_id} for {team}")
            game_state.set_position_player(team, position, new_player_id)
            return

    # If the old player is the pitcher, replace the pitcher
    if old_player_id == current_pitcher or current_pitcher is None:
        print(f"Replacing pitcher for {team}: {old_player_id} with {new_player_id}")
        if team == 'home':
            game_state.home_pitcher = new_player_id
        else:
            game_state.away_pitcher = new_player_id


def _replace_in_batting_order(game_state, team, old_player_id, new_player_id):
    lineup = game_state.home_lineup if team == 'home' else game_state.away_lineup

    # Find the old player in the batting lineup and replace them with the new player
    for idx, player_id in enumerate(lineup):
        if player_id == old_player_id:
            lineup[idx] = new_player_id
            print(f"Replaced {old_player_id} with {new_player_id} in the {team} batting order at position {idx}.")
            return


def remove_middle_initials(name):
    # Pattern to match names with one or more middle initials (case insensitive)
    pattern = r'^(\w+)\s+(?:[A-Za-z]\.?\s+)+(\w+)$'

    match = re.match(pattern, name)
    if match:
        # If the pattern matches, return the name without middle initials
        return f"{match.group(1)} {match.group(2)}"
    else:
        # If the pattern doesn't match, return the original name
        return name


# Dictionary mapping event types to their handler functions
event_handlers = {
    "Groundout": handle_out,
    "Flyout": handle_out,
    "Strikeout": handle_out,
    "Lineout": handle_out,
    "Fielders Choice Out": handle_out,
    "Pop Out": handle_out,
    "Forceout": handle_out,
    "Stolen Base 2B": handle_stolen_base,
    "Stolen Base 3B": handle_stolen_base,
    "Stolen Base Home": handle_stolen_base,
    "Wild Pitch": handle_wild_pitch,
    "Passed Ball": handle_passed_ball,
    "Balk": handle_balk,
    "Pickoff Error 1B": handle_pickoff_error_1b,
    "Pickoff Error 2B": handle_pickoff_error_2b,
    "Pickoff Error 3B": handle_pickoff_error_3b,
    "Pitching Substitution": handle_pitching_sub,
    "Defensive Sub": handle_defensive_sub,
    "Defensive Switch": handle_defensive_switch,
    "Offensive Substitution": handle_offensive_sub,
}

if __name__ == "__main__":
    game_state = GameState()
    handle_pitching_sub('Pitching Change: Michael Fulmer replaces Mark Leiter Jr.', game_state, {})


# TODO: switch up how I'm tying the pitcher and DH together when they lose the DH, they really should just lose their DH completely like it should be set to null

# TODO: handle this crazy event Offensive Substitution: Pinch-runner Gunnar Henderson replaces Ramon Urias.
# Offensive Substitution: Pinch-hitter Ryan O'Hearn replaces James McCann.
