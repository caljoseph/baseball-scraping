import re
import string

from game_state import Base, Half, FieldPosition


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


def handle_stolen_base(description, game_state, player_map):
    # Reverse the player_map to look up player ID by name (using case-insensitive comparison)
    reversed_player_map = {name.lower(): player_id for player_id, name in player_map.items()}

    # Extract player name from description (e.g., 'Elly De La Cruz steals (14) 2nd base.')
    player_name = description.split(" steals")[0].strip().lower()

    # Check if the player exists in the reversed player map
    if player_name not in reversed_player_map:
        return f"Error: Player '{player_name}' not found in player map."

    player_id = reversed_player_map[player_name]

    # Check if the player is currently on any base
    current_base = None
    for base, occupant in game_state.bases_occupied.items():
        if occupant == player_id:
            current_base = base
            break

    if not current_base:
        return f"Error: Player '{player_name}' (ID: {player_id}) not found on any base."

    # Determine the new base based on the type of stolen base
    if "2nd base" in description:
        new_base = Base.SECOND
    elif "3rd base" in description:
        new_base = Base.THIRD
    elif "home" in description:
        new_base = None  # Stealing home means scoring

    # Handle the base update
    if new_base:
        # Clear the player from their current base and move to the new base
        game_state.bases_occupied[current_base] = -1
        game_state.bases_occupied[new_base] = player_id
        return f"Player '{player_name}' (ID: {player_id}) successfully stole {new_base.name.lower()}."

    else:
        # Stealing home: increment score and clear the base
        game_state.bases_occupied[current_base] = -1
        return f"Player '{player_name}' (ID: {player_id}) successfully stole home. Score updated."


def handle_wild_pitch(description, game_state, player_map):
    # Replace periods in known abbreviations with placeholders
    abbreviations = ['Jr.', 'Sr.', 'II', 'III', 'IV', 'V']
    for abbr in abbreviations:
        description = description.replace(abbr, abbr.replace('.', '<dot>'))

    # Now split on '. '
    sentences = description.split('. ')
    # Restore the periods in abbreviations
    sentences = [s.replace('<dot>', '.') for s in sentences]

    pitcher_info = sentences[0]  # Part describing the wild pitch by the pitcher
    base_runner_info = sentences[1:]  # Remaining sentences describe runner movements

    # Reverse the player_map for easier name-based lookup (case-insensitive)
    reversed_player_map = {name.lower(): player_id for player_id, name in player_map.items()}

    # Process base runner movements
    for runner_info in base_runner_info:
        runner_info = runner_info.strip().rstrip('.')

        if not runner_info:
            continue  # Skip empty strings

        if "scores" in runner_info:
            # Handle the case where the runner scores
            runner_name = runner_info.replace(" scores", "").strip().lower()

            if runner_name in reversed_player_map:
                player_id = reversed_player_map[runner_name]
            else:
                return f"Error: Player '{runner_name}' not found in player map."

            current_base = next(
                (base for base, occupant in game_state.bases_occupied.items() if occupant == player_id),
                None
            )

            if not current_base:
                return f"Error: Player '{runner_name}' (ID: {player_id}) not found on any base."

            game_state.bases_occupied[current_base] = -1
            # Update the score if needed
            print(f"Player '{runner_name}' (ID: {player_id}) scored.")

        elif " to " in runner_info:
            # Handle the case where the runner advances to a base
            runner_name, base_movement = runner_info.rsplit(" to ", 1)

            runner_name = runner_name.strip().lower()

            if runner_name in reversed_player_map:
                player_id = reversed_player_map[runner_name]
            else:
                return f"Error: Player '{runner_name}' not found in player map."

            current_base = next(
                (base for base, occupant in game_state.bases_occupied.items() if occupant == player_id),
                None
            )

            if not current_base:
                return f"Error: Player '{runner_name}' (ID: {player_id}) not found on any base."

            if "2nd" in base_movement or "second" in base_movement:
                new_base = Base.SECOND
            elif "3rd" in base_movement or "third" in base_movement:
                new_base = Base.THIRD
            else:
                return f"Error: Unrecognized base movement for '{runner_name}': '{base_movement}'"

            game_state.bases_occupied[current_base] = -1
            game_state.bases_occupied[new_base] = player_id
            print(f"Player '{runner_name}' (ID: {player_id}) moved to {new_base.name.lower()}.")

        else:
            # Handle other cases if necessary
            continue

    return None  # No errors, return None


def handle_passed_ball(description, game_state, player_map):
    # Extract catcher and base runner information from the description
    parts = description.split(". ")
    catcher_info = parts[0]  # The part describing the passed ball by the catcher
    base_runner_info = parts[1:]  # The part(s) describing the runner movements

    # Reverse the player_map for easier name-based lookup (case-insensitive)
    reversed_player_map = {name.lower(): player_id for player_id, name in player_map.items()}

    # Process base runner movements
    runner_movements = []
    for runner_info in base_runner_info:
        runner_info = runner_info.strip()
        if "scores" in runner_info:
            runner_name = runner_info.replace(" scores", "").strip().lower()
            runner_movements.append((runner_name, "scores"))
        elif " to " in runner_info:
            runner_name, base_movement = runner_info.split(" to ")
            runner_name = runner_name.strip().lower()
            runner_movements.append((runner_name, base_movement.strip()))

    # Sort runner movements: scores first, then 3rd, then 2nd
    runner_movements.sort(key=lambda x: (
        0 if x[1] == "scores" else
        1 if "3rd" in x[1] else
        2 if "2nd" in x[1] else 3
    ))

    # Process runner movements in the sorted order
    for runner_name, movement in runner_movements:
        if runner_name in reversed_player_map:
            player_id = reversed_player_map[runner_name]
        else:
            print(f"Error: Player '{runner_name}' not found in player map.")
            continue

        # Find the current base of the player
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

    return None


def handle_balk(description, game_state, player_map):
    # Ensure that the description contains "on a balk"
    if "on a balk" not in description:
        return "Error: Not a valid balk event description."

    # Split the description at "batting," to focus on the part where runners advance
    if "batting," in description:
        parts = description.split("batting, ")[1]  # Get the part after "batting,"
    else:
        return "Error: Malformed balk description."

    # Now we split at " on a balk" to extract individual runner movements
    base_runner_info = parts.split(" on a balk. ")

    # Reverse the player_map for easier name-based lookup (case-insensitive)
    reversed_player_map = {name.lower(): player_id for player_id, name in player_map.items()}

    # Process each runner movement
    for runner_info in base_runner_info:
        runner_info = runner_info.strip()

        # Example: "Zack Short advances to 3rd."
        if "advances to" in runner_info:
            # Handle the case where the runner advances to a base
            runner_name, base_movement = runner_info.split(" advances to ")

            runner_name = runner_name.strip().lower()

            # If the player is in the map, get their player ID
            if runner_name in reversed_player_map:
                player_id = reversed_player_map[runner_name]
            else:
                return f"Error: Player '{runner_name}' not found in player map."

            # Find the current base of the player
            current_base = None
            for base, occupant in game_state.bases_occupied.items():
                if occupant == player_id:
                    current_base = base
                    break

            if not current_base:
                return f"Error: Player '{runner_name}' (ID: {player_id}) not found on any base."

            # Determine the target base
            if "2nd" in base_movement:
                new_base = Base.SECOND
            elif "3rd" in base_movement:
                new_base = Base.THIRD
            elif "scores" in base_movement:
                new_base = None  # The runner scores
            else:
                return f"Error: Unrecognized base movement for '{runner_name}': '{base_movement}'"

            # Handle the base update
            if new_base:
                # Clear the player from their current base and move to the new base
                game_state.bases_occupied[current_base] = -1
                game_state.bases_occupied[new_base] = player_id
                print(f"Player '{runner_name}' (ID: {player_id}) moved to {new_base.name.lower()}.")
            else:
                # If the player scores, remove them from the base (scoring handled elsewhere)
                game_state.bases_occupied[current_base] = -1
                print(f"Player '{runner_name}' (ID: {player_id}) scored.")

    return None  # No errors, return None


def handle_pickoff_error_1b(description, game_state, player_map):
    print("Handling Pickoff Error 1B")

    # Reverse the player_map for case-insensitive name lookup
    reversed_player_map = {name.lower(): player_id for player_id, name in player_map.items()}

    # Track players who have scored to avoid putting them back on a base
    scored_players = []

    # Extract any player names mentioned in the description for scoring
    if "scores" in description:
        # Find the player's name who scores
        for player_name in reversed_player_map.keys():
            if player_name in description.lower():
                player_id = reversed_player_map[player_name]

                # Remove the player from their base
                for base, occupant in game_state.bases_occupied.items():
                    if occupant == player_id:
                        game_state.bases_occupied[base] = -1
                        scored_players.append(player_id)
                        print(f"Player '{player_name}' (ID: {player_id}) scored.")
                        break

    # Handle base advancements, skipping scored players
    runner_on_first = game_state.bases_occupied[Base.FIRST]
    runner_on_second = game_state.bases_occupied[Base.SECOND]

    # If there's a runner on 1st and they haven't scored, move them to 2nd
    if runner_on_first != -1 and runner_on_first not in scored_players:
        game_state.bases_occupied[Base.FIRST] = -1
        game_state.bases_occupied[Base.SECOND] = runner_on_first
        print(f"Runner on 1st advanced to 2nd. (Player ID: {runner_on_first})")

    # If there's a runner on 2nd and they haven't scored, move them to 3rd
    if runner_on_second != -1 and runner_on_second not in scored_players:
        game_state.bases_occupied[Base.SECOND] = -1
        game_state.bases_occupied[Base.THIRD] = runner_on_second
        print(f"Runner on 2nd advanced to 3rd. (Player ID: {runner_on_second})")


def handle_pickoff_error_2b(description, game_state, player_map):
    print("Handling Pickoff Error 2B")

    # Reverse the player_map for case-insensitive name lookup
    reversed_player_map = {name.lower(): player_id for player_id, name in player_map.items()}

    # Track players who have scored to avoid putting them back on a base
    scored_players = []

    # Extract any player names mentioned in the description for scoring
    if "scores" in description:
        for player_name in reversed_player_map.keys():
            if player_name in description.lower():
                player_id = reversed_player_map[player_name]

                # Remove the player from their base
                for base, occupant in game_state.bases_occupied.items():
                    if occupant == player_id:
                        game_state.bases_occupied[base] = -1
                        scored_players.append(player_id)
                        print(f"Player '{player_name}' (ID: {player_id}) scored.")
                        break

    # Handle base advancements, skipping scored players
    runner_on_second = game_state.bases_occupied[Base.SECOND]
    runner_on_first = game_state.bases_occupied[Base.FIRST]

    # If there's a runner on 2nd and they haven't scored, move them to 3rd
    if runner_on_second != -1 and runner_on_second not in scored_players:
        game_state.bases_occupied[Base.SECOND] = -1
        game_state.bases_occupied[Base.THIRD] = runner_on_second
        print(f"Runner on 2nd advanced to 3rd. (Player ID: {runner_on_second})")

    # If there's a runner on 1st and they haven't scored, move them to 2nd
    if runner_on_first != -1 and runner_on_first not in scored_players:
        game_state.bases_occupied[Base.FIRST] = -1
        game_state.bases_occupied[Base.SECOND] = runner_on_first
        print(f"Runner on 1st advanced to 2nd. (Player ID: {runner_on_first})")


def handle_pickoff_error_3b(description, game_state, player_map):
    print("Handling Pickoff Error 3B")

    # Reverse the player_map for case-insensitive name lookup
    reversed_player_map = {name.lower(): player_id for player_id, name in player_map.items()}

    # Track players who have scored to avoid putting them back on a base
    scored_players = []

    # Extract any player names mentioned in the description for scoring
    if "scores" in description:
        for player_name in reversed_player_map.keys():
            if player_name in description.lower():
                player_id = reversed_player_map[player_name]

                # Remove the player from their base
                for base, occupant in game_state.bases_occupied.items():
                    if occupant == player_id:
                        game_state.bases_occupied[base] = -1
                        scored_players.append(player_id)
                        print(f"Player '{player_name}' (ID: {player_id}) scored.")
                        break


def process_name(name):
    parts = name.split()
    if len(parts) >= 3 and all(len(part) == 2 and part.endswith('.') for part in parts[:-1]):
        name = ''.join(parts[:-1]) + ' ' + parts[-1]

    if name.lower().endswith("jr."):
        name = name.strip()
    else:
        name = name.rstrip(string.punctuation)

    # Replace "joshua" or "Joshua" with "josh"
    name = name.replace("joshua", "josh").replace("Joshua", "josh")

    return remove_middle_initials(name.lower())


def get_player_id(player_name, player_map):
    print(f"Attempting to get player ID for: {player_name}")

    reversed_player_map = {process_name(name): player_id for player_id, name in player_map.items()}

    player_id = reversed_player_map.get(player_name)

    if player_id:
        print(f"Found player ID: {player_id}")
    else:
        print(f"No player ID found for {player_name}")

    return player_id


def handle_offensive_sub(description, game_state, player_map):
    match = re.search(r'(?:runner|hitter)\s+(.+?)\s+replaces\s+(.+?)$', description, re.IGNORECASE)
    if not match:
        print(f"Error: Could not parse player names from description: {description}")
        return

    new_player_name = match.group(1).strip()
    old_player_name = match.group(2).strip()

    print(f"New player name before processing: {new_player_name}")
    print(f"Old player name before processing: {old_player_name}")

    new_player_name = process_name(new_player_name)
    old_player_name = process_name(old_player_name)

    print(f"New player name after processing: {new_player_name}")
    print(f"Old player name after processing: {old_player_name}")

    new_player_id = get_player_id(new_player_name, player_map)
    old_player_id = get_player_id(old_player_name, player_map)

    if not new_player_id or not old_player_id:
        print(f"Warning: Could not find one or both players in the player map: {new_player_name}, {old_player_name}")
        return

    team = 'away' if game_state.half == Half.TOP else 'home'

    _replace_in_batting_order(game_state, team, old_player_id, new_player_id)
    _replace_position_player(game_state, team, old_player_id, new_player_id)

    if "Pinch-runner" in description:
        _replace_on_base(game_state, old_player_id, new_player_id)
        print(
            f"Pinch-runner: {new_player_name} (ID: {new_player_id}) replaces {old_player_name} (ID: {old_player_id}) on the base paths.")
    else:
        print(
            f"Pinch-hitter: {new_player_name} (ID: {new_player_id}) replaces {old_player_name} (ID: {old_player_id}) in the batting order.")


def handle_pitching_sub(description, game_state, player_map):
    if "enters the batting order" in description:
        parts = description.split()
        new_player_name = process_name(' '.join(parts[1:3]))
        old_player_name = process_name(' '.join(parts[-5:-3]))
        batting_position = parts[parts.index("batting") + 1].rstrip(',')

        new_player_id = get_player_id(new_player_name, player_map)
        old_player_id = get_player_id(old_player_name, player_map)

        if not new_player_id or not old_player_id:
            print(
                f"Warning: Unable to find one or both players in player map. New: '{new_player_name}', Old: '{old_player_name}'")
            return

        team = 'home' if game_state.half == Half.TOP else 'away'
        print(f"Replacing {old_player_name} with {new_player_name} in the batting order at position {batting_position}")
        _replace_in_batting_order(game_state, team, old_player_id, new_player_id)
        return

    match = re.match(r"Pitching Change:\s*(.+?)\s+replaces\s+(.+?)(?:,\s*batting.*)?\.?$", description)
    if not match:
        print(f"Warning: Unable to parse pitching substitution description: '{description}'")
        return

    new_pitcher_name = process_name(match.group(1))
    old_pitcher_name = process_name(match.group(2))

    new_pitcher_id = get_player_id(new_pitcher_name, player_map)
    old_pitcher_id = get_player_id(old_pitcher_name, player_map)

    if not new_pitcher_id or not old_pitcher_id:
        print(
            f"Warning: Unable to find one or both pitchers in player map. New: '{new_pitcher_name}', Old: '{old_pitcher_name}'")
        return

    team = 'home' if game_state.half == Half.TOP else 'away'
    print(f"Attempting to replace pitcher, {old_pitcher_name} with {new_pitcher_name}")
    _replace_position_player(game_state, team, old_pitcher_id, new_pitcher_id)

    if not getattr(game_state, f"{team}_has_dh"):
        _replace_in_batting_order(game_state, team, old_pitcher_id, new_pitcher_id)
    else:
        print(f"{team.capitalize()} team has a DH, no need to update the batting order for the pitcher.")


def handle_defensive_sub(description, game_state, player_map):
    new_player_name, old_player_name = _extract_players_from_def_sub_desc(description)
    new_player_id = get_player_id(new_player_name.lower(), player_map)
    old_player_id = get_player_id(old_player_name.lower(), player_map)

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
    if "remains in the game" in description:
        print("No defensive switch required as the player remains in the game.")
        return

    from_position_name = description.split("switch from ")[1].split(" to ")[0].strip().lower()
    to_position_name = description.split(" to ")[1].split(" for ")[0].strip().lower()
    player_name_part = description.split("for")[1].strip()

    player_name = process_name(player_name_part)
    player_id = get_player_id(player_name, player_map)

    if not player_id:
        print(f"Warning: Player '{player_name}' not found in the player map.")
        return

    team = 'home' if game_state.half == Half.TOP else 'away'

    # Special case for Ohtani (or any pitcher to DH switch)
    if from_position_name == 'pitcher' and to_position_name == 'designated hitter':
        from_position = FieldPosition.DESIGNATED_HITTER  # We'll treat pitcher as DH for this swap
        to_position = FieldPosition.DESIGNATED_HITTER
        print(f"Special case: {player_name} switching from pitcher to designated hitter.")
    else:
        from_position = FieldPosition[from_position_name.replace(" ", "_").upper()]
        to_position = FieldPosition[to_position_name.replace(" ", "_").upper()]

    position_players = game_state.home_position_players if team == 'home' else game_state.away_position_players

    if from_position == FieldPosition.DESIGNATED_HITTER or to_position == FieldPosition.DESIGNATED_HITTER:
        setattr(game_state, f"{team}_has_dh", True)  # Ensure DH is set to True in this case
        print(f"{team.capitalize()} team is using a DH as '{player_name}' is now the designated hitter.")

    # For the Ohtani case, we're essentially just updating the DH position
    if from_position == FieldPosition.DESIGNATED_HITTER and to_position == FieldPosition.DESIGNATED_HITTER:
        position_players[FieldPosition.DESIGNATED_HITTER] = player_id
        print(f"Updated designated hitter to {player_name} for {team} team.")
    else:
        player_in_from_position = position_players[from_position]
        player_in_to_position = position_players[to_position]

        position_players[from_position] = player_in_to_position
        position_players[to_position] = player_in_from_position

        print(
            f"Player '{player_name}' moved from {from_position.name.lower()} to {to_position.name.lower()} for {team}.")
        print(f"Swapped players: {player_in_from_position} <-> {player_in_to_position}")

    # Update pitcher if necessary
    # if from_position_name == 'pitcher':
    #     setattr(game_state, f"{team}_pitcher", None)  # Clear the current pitcher
    #     print(f"Cleared pitcher for {team} team as {player_name} moved to DH.")
    # elif to_position_name == 'pitcher':
    #     setattr(game_state, f"{team}_pitcher", player_id)
    #     print(f"Set {player_name} as the new pitcher for {team} team.")


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


def _replace_in_batting_order(game_state, team, old_player_id, new_player_id):
    lineup = game_state.home_lineup if team == 'home' else game_state.away_lineup

    # We check if the team lost their DH then we need to apply this replacement to both the pitcher and the DH
    if not getattr(game_state, f"{team}_has_dh"):
        # Check if the old player is the current pitcher and replace them in the batting order
        old_pitcher = game_state.home_pitcher if team == 'home' else game_state.away_pitcher
        if old_player_id == old_pitcher:
            for idx, player_id in enumerate(lineup):
                if player_id == old_player_id:
                    lineup[idx] = new_player_id
                    print(
                        f"Replaced pitcher/DH {old_player_id} with {new_player_id} in the {team} batting order at position {idx}.")
                    return

    # Find the old player in the batting lineup
    for idx, player_id in enumerate(lineup):
        if player_id == old_player_id:
            lineup[idx] = new_player_id
            print(f"Replaced {old_player_id} with {new_player_id} in the {team} batting order at position {idx}.")
            return


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
        has_dh = game_state.home_has_dh
        current_pitcher = game_state.home_pitcher
        current_dh = game_state.get_position_player(team, FieldPosition.DESIGNATED_HITTER)
    elif team == 'away':
        position_players = game_state.away_position_players
        has_dh = game_state.away_has_dh
        current_pitcher = game_state.away_pitcher
        current_dh = game_state.get_position_player(team, FieldPosition.DESIGNATED_HITTER)
    else:
        raise ValueError("Team must be 'home' or 'away'")

    print(" current_pitcher: ", current_pitcher)
    print(" current_dh: ", current_dh)

    # This will determine if we need to perform the same action on both the pitcher and DH
    # Assuming the replacement even involves one of them
    if not has_dh:
        # Check if we're replacing pitcher or DH
        if old_player_id == current_pitcher or old_player_id == current_dh:
            # Replace both the pitcher and the DH with the new player
            print(f"Replacing pitcher and DH for {team}: {old_player_id} with {new_player_id}")
            game_state.set_position_player(team, FieldPosition.DESIGNATED_HITTER, new_player_id)
            if team == 'home':
                game_state.home_pitcher = new_player_id
            else:
                game_state.away_pitcher = new_player_id
            return

    # If the old player is a position player, replace them in their field position
    for position, player_id in position_players.items():
        if player_id == old_player_id:
            print(f"Replacing {old_player_id} at {position} with {new_player_id} for {team}")
            game_state.set_position_player(team, position, new_player_id)
            return

    # If the old player is the pitcher, replace the pitcher
    if old_player_id == current_pitcher:
        print(f"Replacing pitcher for {team}: {old_player_id} with {new_player_id}")
        if team == 'home':
            game_state.home_pitcher = new_player_id
        else:
            game_state.away_pitcher = new_player_id


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

# if __name__ == "__main__":

