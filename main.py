import re
import traceback
from scraper import setup_webdriver, process_box, process_summary, GameData
from game_state import GameState, FieldPosition
from game_state import Half as Half
from game_state import Base as Base
from event_handlers import event_handlers
from csv_utils import initialize_csv, write_decision_point_to_csv
from statcast_at_bats import get_at_bat_summary_for_game
from event_handlers import process_name, get_closest_player_id
import json
import os
from pathlib import Path
import pandas as pd

class GameProcessor:
    def __init__(self, scraped_dir: str = "scraped_games"):
        self.scraped_dir = Path(scraped_dir)
        if not self.scraped_dir.exists():
            raise ValueError(f"Scraped games directory {scraped_dir} does not exist")

    def load_game_data(self, game_pk: str) -> GameData:
        """Load game data from storage"""
        game_path = self.scraped_dir / f"game_{game_pk}.json"
        if not game_path.exists():
            raise ValueError(f"No data found for game {game_pk}")

        with open(game_path) as f:
            data = json.load(f)
            return GameData(**data)


def create_dataset(num_games: int, input_csv: str, scraped_data_dir: str = "scraped_games"):
    """Modified version of your create_dataset function that works with stored data"""
    game_url_df = pd.read_csv(input_csv)
    os.makedirs('games', exist_ok=True)
    error_log = []
    processor = GameProcessor(scraped_data_dir)
    with open('helper_files/statcast_reduced2023.csv', 'r') as f:
        input_csv = f.read()

    for index, row in game_url_df.iterrows():
        if index >= num_games:
            break

        game_pk = row['game_pk']
        try:
            print(f"\nProcessing game {game_pk}")
            game_data = processor.load_game_data(str(game_pk))
            print("Successfully loaded game data")

            at_bat_summary = get_at_bat_summary_for_game(input_csv, str(game_pk))

            # Convert player IDs to integers where needed
            home_lineup = [int(player_id) if isinstance(player_id, str) else player_id
                         for player_id in game_data.home_lineup]
            away_lineup = [int(player_id) if isinstance(player_id, str) else player_id
                         for player_id in game_data.away_lineup]
            home_bullpen = [int(player_id) if isinstance(player_id, str) else player_id
                          for player_id in game_data.home_bullpen]
            away_bullpen = [int(player_id) if isinstance(player_id, str) else player_id
                          for player_id in game_data.away_bullpen]

            # Initialize GameState
            game_state = GameState(
                home_abbr=game_data.home_abbr,
                away_abbr=game_data.away_abbr,
                home_lineup=home_lineup,
                away_lineup=away_lineup,
                home_pitcher=home_bullpen[0] if home_bullpen else None,
                home_sub_ins=home_bullpen,
                away_pitcher=away_bullpen[0] if away_bullpen else None,
                away_sub_ins=away_bullpen,
            )

            # Make sure the lineups are properly set
            game_state.home_lineup = home_lineup
            game_state.away_lineup = away_lineup

            # Convert position maps to use integer keys
            home_position_map = {int(k): v for k, v in game_data.home_position_map.items()}
            away_position_map = {int(k): v for k, v in game_data.away_position_map.items()}

            # Initialize positions
            for team, lineup, position_map in [
                ('home', home_lineup, home_position_map),
                ('away', away_lineup, away_position_map)
            ]:
                print(f"\nSetting up {team} team positions:")
                for player_id in lineup:
                    position = position_map.get(player_id)
                    print(f"  Player {player_id} position: {position}")
                    field_position = next((fp for fp in FieldPosition if fp.value == position), None)
                    if field_position:
                        game_state.set_position_player(team, field_position, player_id)
                        print(f"    Set {player_id} to {field_position.name}")

            # Convert player maps to use integer keys
            home_player_map = {int(k) if isinstance(k, str) else k: v
                             for k, v in game_data.home_player_map.items()}
            away_player_map = {int(k) if isinstance(k, str) else k: v
                             for k, v in game_data.away_player_map.items()}

            # Print initial state for verification
            print_initial_game_state(game_state, home_player_map, away_player_map)

            output_filename = f'games/game_{game_pk}_decisions.csv'
            initialize_csv(output_filename)

            # Combine player maps
            player_map = {**home_player_map, **away_player_map}

            for inning in game_data.game_summary:
                inning_str = inning['inning']
                half_str, inning_number_str = inning_str.split()
                inning_number = int(inning_number_str[:-2])
                half = Half.TOP if half_str == 'Top' else Half.BOTTOM

                for event in inning['events']:
                    process_event(event, game_state, player_map, output_filename,
                                at_bat_summary, inning_number, half)

        except Exception as e:
            error_message = f"Error processing game {game_pk}: {str(e)}\n{traceback.format_exc()}"
            print(error_message)
            error_log.append(error_message)

    if error_log:
        with open('game_processing_errors.log', 'w') as f:
            for error in error_log:
                f.write(f"{error}\n\n")
def print_initial_game_state(game_state, home_player_map, away_player_map):
    print("\nInitial Game State:")
    print(f"Inning: {game_state.inning} {game_state.half.name}")
    print(f"Score: Away {game_state.score_away} - Home {game_state.score_home}")
    print(f"Outs: {game_state.outs}")
    print(f"Bases: {game_state.bases_occupied}")
    print(f"Away Lineup: {[away_player_map.get(player_id, 'Unknown') for player_id in game_state.away_lineup]}")
    print(f"Home Lineup: {[home_player_map.get(player_id, 'Unknown') for player_id in game_state.home_lineup]}")
    print(f"Away Pitcher: {away_player_map.get(game_state.away_pitcher, 'Unknown')}")
    print(f"Away Sub Ins: {game_state.away_sub_ins}")
    print(f"Home Pitcher: {home_player_map.get(game_state.home_pitcher, 'Unknown')}")
    print(f"Home Sub Ins: {game_state.home_sub_ins}")

    print("\nInitial Positions:")
    for team in ['home', 'away']:
        print(f"{team.capitalize()} Team:")
        for pos in FieldPosition:
            player_id = game_state.get_position_player(team, pos)
            if player_id is not None:
                player_name = home_player_map.get(player_id, 'Unknown') if team == 'home' else away_player_map.get(
                    player_id, 'Unknown')
            else:
                player_name = 'None'
            print(f"  {pos.name}: {player_name}")

    print("\nInitial Mappings:")
    print("Home Team:")
    for player_id, player_name in home_player_map.items():
        print(f"  {player_name}: {player_id}")

    print("\nAway Team:")
    for player_id, player_name in away_player_map.items():
        print(f"  {player_name}: {player_id}")


def process_event(event, game_state, player_map, csv_filename, at_bat_summary, inning_number, half):
    # if these two are different it's a new inning, and we need to reset outs
    if game_state.inning != inning_number:
        game_state.outs = 0
    # Set the game state inning and half
    game_state.inning = inning_number
    game_state.half = half

    print("Event info:")
    print(f"Inning: {inning_number}")
    print("   type: ", event['type'])
    print("   description: ", event['description'])
    print("   at bat: ", event['atbat_index'])
    print("   outs update: ", event['outs_update'])
    print("   score update: ", event['score_update'])
    print("   gamestate.atbat: ", game_state.at_bat)
    print("   gamestate.inning: ", game_state.inning)
    print("   gamestate.half: ", game_state.half)
    print("   gamestate.outs: ", game_state.outs)


    # Check if we can verify our bases before saving off the event
    event_at_bat = event['atbat_index']
    if game_state.at_bat != event_at_bat and event['type'] != 'Intent Walk':
        # We're on a new at bat and can trust statcast
        previous_at_bat = game_state.at_bat
        game_state.at_bat = event_at_bat

        is_offensive_sub = event['type'] == 'Offensive Substitution'

        # the only time when I shouldn't trust synchronize bases is for pickoff caught stealing base and caught stealing base events
        # because they have the same at bat number as the following event which is going to overwrite their base configuration
        # and make it so it looks like the runner was already caught out before the event occurs.
        # we must have a flag we pass in
        is_caught_stealing = event['type'] in caught_stealing_events

        synchronize_bases(game_state, at_bat_summary, is_offensive_sub, is_caught_stealing, event, player_map)


        # Verify and correct previous at-bat's base configurations
        if not is_caught_stealing:
            verify_previous_at_bat_bases(csv_filename, previous_at_bat, game_state)

    # We label decision events from chance events
    is_decision = event['type'] in decision_events

    # But we need to handle the exceptions where it might have really been a bunt
    # Or check whether an injury resulted in a player leaving a game
    if event['type'] in possible_decision_events:
        is_decision = verify_decision(event, game_state)


    # Save off the pre-event game state to the csv
    decision_point = game_state.create_decision_point(event, is_decision, player_map)
    write_decision_point_to_csv(csv_filename, decision_point)

    # Get the handler and modify the game_state
    event_type = event['type']
    handler = event_handlers.get(event_type)
    if handler:
        result = handler(event['description'], game_state, player_map)
        if result:
            print(result)
    else:
        print(f"Unhandled event type: {event_type}. {event['description']}")

    # Update the scores if a score change was reported
    if event['score_update']:
        game_state.score_away = event['score_update'][game_state.away_abbr]
        game_state.score_home = event['score_update'][game_state.home_abbr]

    # Update the outs if an out change was reported
    if event['outs_update']:
        game_state.outs = event['outs_update']

    if game_state.outs == 3:
        game_state.outs = 0


def synchronize_bases(game_state, at_bat_summary, is_offensive_sub, is_caught_stealing, event, player_map):
    at_bat_summary.head()
    current_half = 'Top' if game_state.half == Half.TOP else 'Bot'
    current_at_bat = at_bat_summary[(at_bat_summary['inning'].astype(str) == str(game_state.inning)) &
                                    (at_bat_summary['inning_topbot'].astype(str) == current_half) &
                                    (at_bat_summary['at_bat_number'].astype(str) == str(game_state.at_bat))]

    if current_at_bat.empty:
        print(f"Warning: statcast does not contain an at bat for {game_state.at_bat}")
        return

    current_at_bat_row = current_at_bat.iloc[0]

    new_bases_occupied = {
        Base.FIRST: int(current_at_bat_row['on_1b']) if pd.notna(current_at_bat_row['on_1b']) else -1,
        Base.SECOND: int(current_at_bat_row['on_2b']) if pd.notna(current_at_bat_row['on_2b']) else -1,
        Base.THIRD: int(current_at_bat_row['on_3b']) if pd.notna(current_at_bat_row['on_3b']) else -1
    }

    # Special handling for caught stealing and pickoff caught stealing events
    if is_caught_stealing:
        # Extract player information from the event description
        player_name = extract_player_name(event['description'])
        player_id = get_closest_player_id(player_name, player_map)
        base_to_check, target_base = determine_base_from_description(event['description'])

        if player_id:
            # Check if the player is already on the expected base
            runner_on_base = game_state.bases_occupied.get(base_to_check, -1)
            if runner_on_base != player_id:
                # Player was not found on the expected base; trust the event description
                print(f"Adjusting bases: Placing player '{player_name}' (ID: {player_id}) on {base_to_check.name}")
                new_bases_occupied[base_to_check] = player_id

    if is_offensive_sub and "runner" in event['description']:
        # Reverse the base update for pinch-runners
        old_player_name = event['description'].split("replaces")[1].strip().rstrip('.').lower()
        new_player_name = re.search(r'runner\s+(.+?)\s+replaces', event['description'], re.IGNORECASE).group(1).lower()

        reversed_player_map = {name.lower(): player_id for player_id, name in player_map.items()}
        old_player_id = reversed_player_map.get(old_player_name)
        new_player_id = reversed_player_map.get(new_player_name)

        if old_player_id and new_player_id:
            for base, player_id in new_bases_occupied.items():
                if player_id == new_player_id:
                    new_bases_occupied[base] = old_player_id
                    print(f"Reversed pinch-runner substitution: {old_player_name} (ID: {old_player_id}) back on {base}")

    game_state.bases_occupied = new_bases_occupied


def verify_previous_at_bat_bases(csv_filename, previous_at_bat, current_game_state):
    # Part 1: This will help us to set the record straight on where our assumptions went bad
    # when handling pick-off errors
    df = pd.read_csv(csv_filename)

    # Filter rows for the previous at-bat
    previous_at_bat_rows = df[df['At_Bat'] == previous_at_bat]
    if previous_at_bat_rows.empty:
        return

    corrections_needed = False
    current_bases = {
        'First_Base': current_game_state.bases_occupied[Base.FIRST],
        'Second_Base': current_game_state.bases_occupied[Base.SECOND],
        'Third_Base': current_game_state.bases_occupied[Base.THIRD]
    }

    # Check each row in the previous at-bat for impossible base configurations
    for index, row in previous_at_bat_rows.iterrows():
        for base, current_runner in current_bases.items():
            if current_runner != -1:
                # Check if this runner was on a more advanced base in the previous at-bat
                if (base == 'First_Base' and
                        (row['Second_Base'] == current_runner or row['Third_Base'] == current_runner)):
                    corrections_needed = True
                    df.at[index, 'Second_Base'] = -1 if row['Second_Base'] == current_runner else df.at[
                        index, 'Second_Base']
                    df.at[index, 'Third_Base'] = -1 if row['Third_Base'] == current_runner else df.at[
                        index, 'Third_Base']
                    df.at[index, 'First_Base'] = current_runner
                elif base == 'Second_Base' and row['Third_Base'] == current_runner:
                    corrections_needed = True
                    df.at[index, 'Third_Base'] = -1
                    df.at[index, 'Second_Base'] = current_runner

            # We don't need to do anything if the runner is not in the current bases
            # This handles the case where a runner has scored or otherwise advanced off the bases

    if corrections_needed:
        # Write the corrected data back to the CSV
        df.to_csv(csv_filename, index=False)
        print(f"Corrected base configurations for at-bat {previous_at_bat}")

    # Part 2: Handle offensive substitutions, this is a bizarre edge case where
    # statcast performs all the offensive subs at the start of the at bat
    # so we need to rely on our position players columns to set the record straight
    df = pd.read_csv(csv_filename)
    at_bat_rows = df[df['At_Bat'] == previous_at_bat]

    offensive_sub_rows = at_bat_rows[at_bat_rows['Event_Type'] == 'Offensive Substitution']

    for index, sub_row in offensive_sub_rows.iterrows():
        if index + 1 < len(df):
            next_row = df.iloc[index + 1]

            # Find the columns that changed (excluding 'Event_Type')
            changed_columns = [col for col in df.columns if col != 'Event_Type' and sub_row[col] != next_row[col]]

            if len(changed_columns) == 2:
                old_player_id = sub_row[changed_columns[0]]
                new_player_id = next_row[changed_columns[0]]
                changed_column = changed_columns[0]

                # Check if the new player is already on base in the substitution row
                bases = ['First_Base', 'Second_Base', 'Third_Base']
                if any(sub_row[base] == new_player_id for base in bases):
                    # Correct the rows before this substitution
                    for prev_index in range(index, -1, -1):
                        prev_row = df.iloc[prev_index]
                        if prev_row['At_Bat'] != previous_at_bat:
                            break

                        # Use the lineup column that contained the old player before the sub as the source of truth
                        if prev_row[changed_column] == old_player_id:
                            for base in bases:
                                if prev_row[base] == new_player_id:
                                    df.at[prev_index, base] = old_player_id

    # Write the corrected data back to the CSV
    df.to_csv(csv_filename, index=False)
    print(f"Corrected offensive substitutions for at-bat {previous_at_bat}")


def verify_decision(event, game_state):
    description = event['description'].lower()

    # Check if the event is an injury and the player left the game
    if event['type'] == 'Injury' and 'left the game' in description:
        print("Found an injury where someone left the game")
        return True

    # Check if the description contains the word 'bunt', bases are not empty, and there are less than two outs
    if (
            'soft bunt' in description and
            any(player_id != -1 for player_id in game_state.bases_occupied.values()) and
            game_state.outs < 2
    ):
        print("Found a bunt with runners on base and less than two outs")
        return True

    return False


def extract_player_name(description):
    """
    Extract the player's name from the event description.
    Handles different formats for caught stealing and pickoff caught stealing events.
    """
    if "picked off" in description.lower():
        # Handle the pickoff format: "Player picked off and caught stealing ..."
        try:
            # Extract the name before "picked off"
            player_name_part = description.split("picked off")[0].strip().split(",")[-1].strip()
        except IndexError:
            print("Warning: Could not extract the player's name for pickoff caught stealing.")
            return None
    elif "caught stealing" in description.lower():
        # Handle the caught stealing format
        try:
            if ":" in description:
                # Format: "Team challenged ..., call on the field was overturned: Player caught stealing ..."
                player_name_part = description.split(":")[1].split("caught stealing")[0].strip()
            else:
                # Format: "Player caught stealing ..."
                player_name_part = description.split("caught stealing")[0].strip()
        except IndexError:
            print("Warning: Could not extract the player's name for caught stealing.")
            return None
    else:
        print("Warning: Description does not match expected formats for caught stealing or pickoff caught stealing.")
        return None

    # Process and clean the extracted name
    return process_name(player_name_part)


def determine_base_from_description(description):
    if "2nd base" in description.lower():
        return Base.FIRST, "2B"
    elif "3rd base" in description.lower():
        return Base.SECOND, "3B"
    elif "home" in description.lower():
        return Base.THIRD, "Home"
    else:
        print("Error: Could not determine which base the player was attempting to steal.")
        return None, None


decision_events = [
    'Pitching Substitution',
    'Offensive Substitution',
    'Defensive Switch',
    'Stolen Base 2B',
    'Defensive Sub',
    'Caught Stealing 2B',
    'Stolen Base 3B',
    'Intent Walk',
    'Sac Bunt',
    'Bunt Groundout',
    'Pickoff Caught Stealing 2B',
    'Bunt Pop Out',
    'Caught Stealing 3B',
    'Caught Stealing Home',
    'Pickoff Caught Stealing 3B',
    'Stolen Base Home',
    'Bunt Lineout',
    'Pickoff Caught Stealing Home',
    'Ejection',
]

possible_decision_events = [
    'Single',
    'Double',
    'Triple',
    'Injury'
]

caught_stealing_events = [
    "Pickoff Caught Stealing 2B",
    "Pickoff Caught Stealing 3B",
    "Pickoff Caught Stealing Home",
    "Caught Stealing 2B",
    "Caught Stealing 3B",
    "Caught Stealing Home",
]


# Now that we have the entire 2023 season scraped, the url you input here only determines which game ids we process
if __name__ == "__main__":
    num_games = 300
    url_file_name = "urls/gameday_urls2023.csv"
    create_dataset(num_games, url_file_name)


# TODO: Occasionally in mid at bat events like caught stolen base, that event will report the outs of the next event before those outs
#  are truly there. https://www.mlb.com/gameday/brewers-vs-d-backs/2023/04/11/718611/final/summary/all