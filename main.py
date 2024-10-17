import os
import pandas as pd
import re
import traceback
from scraper import setup_webdriver, process_box, process_summary
from game_state import GameState, FieldPosition
from game_state import Half as Half
from game_state import Base as Base
from event_handlers import event_handlers
from csv_utils import initialize_csv, write_decision_point_to_csv
from statcast_at_bats import get_at_bat_summary_for_game


def create_dataset(num_games):
    driver = setup_webdriver()
    game_url_df = pd.read_csv("urls/single_game.csv")
    os.makedirs('games', exist_ok=True)
    error_log = []

    try:
        for index, row in game_url_df.iterrows():
            if index >= num_games:
                break

            game_pk = row['game_pk']
            box_url = row['box_url']
            summary_url = row['summary_url']
            home_abbr = row['home_abbr']
            away_abbr = row['away_abbr']

            if game_pk != 716558:
                continue

            try:
                # Read the input CSV
                with open('statcast_reduced2023.csv', 'r') as f:
                    input_csv = f.read()

                # Use the statcast adjuster to get the at-bat summary for this game
                at_bat_summary = get_at_bat_summary_for_game(input_csv, str(game_pk))

                # Process all the data from the box summary
                box_data = process_box(driver, box_url)
                away_lineup, away_sub_ins, away_player_map, away_bullpen, away_position_map, \
                    home_lineup, home_sub_ins, home_player_map, home_bullpen, home_position_map = box_data

                # Initialize GameState
                game_state = GameState(
                    home_abbr=home_abbr,
                    away_abbr=away_abbr,
                    home_lineup=home_lineup,
                    away_lineup=away_lineup,
                    home_pitcher=home_bullpen[0],
                    home_sub_ins=home_bullpen,
                    away_pitcher=away_bullpen[0],
                    away_sub_ins=away_bullpen,
                )

                # Initialize positions for both teams
                for team, lineup, position_map in [('home', home_lineup, home_position_map),
                                                   ('away', away_lineup, away_position_map)]:
                    for player_id in lineup:
                        position = position_map[player_id]
                        field_position = next((fp for fp in FieldPosition if fp.value == position), None)
                        if field_position:
                            game_state.set_position_player(team, field_position, player_id)

                # Print initial game state
                print_game_state(game_state, home_player_map, away_player_map)

                # Get the play by play of events
                game_summary = process_summary(driver, summary_url, home_abbr, away_abbr)

                # Initialize the output csv
                output_filename = f'games/game_{game_pk}_decisions.csv'
                initialize_csv(output_filename)

                # Combine player maps for easier lookup
                player_map = {**home_player_map, **away_player_map}

                # Process each event type
                for inning in game_summary:
                    inning_str = inning['inning']
                    half_str, inning_number_str = inning_str.split()
                    inning_number = int(inning_number_str[:-2])
                    half = Half.TOP if half_str == 'Top' else Half.BOTTOM

                    for event in inning['events']:
                        process_event(event, game_state, player_map, output_filename, at_bat_summary, inning_number,
                                      half)

                print(f"Decision points for game {game_pk} have been saved to {output_filename}")

            except Exception as e:
                error_message = f"Error processing game {game_pk}: {str(e)}\n{traceback.format_exc()}"
                print(error_message)
                error_log.append(error_message)

    except Exception as e:
        print(f"An error occurred outside the game processing loop: {e}")
    finally:
        driver.quit()

    # Write error log to file
    if error_log:
        with open('game_processing_errors.log', 'w') as f:
            for error in error_log:
                f.write(f"{error}\n\n")
        print(f"Errors encountered during processing. Check 'game_processing_errors.log' for details.")

    print(f"Processed {min(num_games, len(game_url_df))} games.")


def print_game_state(game_state, home_player_map, away_player_map):
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

    # if these two are different it's a new inning, and we need to reset outs
    if game_state.inning != inning_number:
        game_state.outs = 0
    # Set the game state inning and half
    game_state.inning = inning_number
    game_state.half = half

    # what happened here was that because the offensive sub was in the middle of the at bat, we sunk during the
    # game delay, then when we got to the offensive sub we weren't able to change it back
    # Check if we can verify our bases before saving off the event
    event_at_bat = event['atbat_index']
    if game_state.at_bat != event_at_bat and event['type'] != 'Intent Walk':
        # We're on a new at bat and can trust statcast
        previous_at_bat = game_state.at_bat
        game_state.at_bat = event_at_bat

        is_offensive_sub = event['type'] == 'Offensive Substitution'
        synchronize_bases(game_state, at_bat_summary, is_offensive_sub, event, player_map)

        # Verify and correct previous at-bat's base configurations
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


# TODO now we need to maintain the batting order and handle:
# Offensive Substitution
# Defensive Switch
# Defensive Sub

# When an offensive sub occurs ie a pinch hitter or a pinch runner, when offense and defense next switch there will
# be a corresponding Defensive Switch event for each pinch hitter/runner
# Defensive Switch
# Luis Guillorme remains in the game as the second baseman.
# This is an option, where they just stay in the game. This example Luis stayed in the position he replaced
# but I imagine they could switch to another position

# Defensive Switch
# Defensive switch from second base to left field for Jeff McNeil.
# This example Jeff McNeil was not an offensive sub. I assume this means that we swap the two positions
# The description starts with 'Defensive Switch'

# Defensive Sub
# Defensive Substitution: Omar Narvaez replaces Tim Locastro, batting 9th, playing catcher.
# I believe this one means that Omar Narvaez comes from the bench and we replace Tim's id with his

# There's the scenario where if the DH is put in a different field position then from that point on
# The pitcher is in the batting order
# Of course they could pinch hit and put someone else in, but they would be putting a new pitcher the next half for sure
# We need to notice this situation and handle it as so
#   When performing a defensive sub, we check if the DH is being subbed in.
#   If so then we set a flag on our game_state that from this point on the pitcher and DH are the same person
#   How is that accomplished? We'll probably need a special check in all three of these handlers
#   and handle_pitcher_sub when this flag is set that applies checks if we're modifying the pitcher or DH
#   and wherever one of these methods was used :game_state.away_pitcher or game_state.set_position_player
#   now we'll call both of them

def synchronize_bases(game_state, at_bat_summary, is_offensive_sub, event, player_map):
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

if __name__ == "__main__":
    num_games = 300
    create_dataset(num_games)
    # Redirect stdout to a file
    # log_file = f"output_{num_games}_games.log"
    # with open(log_file, 'w') as f:
    #     sys.stdout = f
    #     create_dataset(num_games)
    #
    # # Reset stdout
    # sys.stdout = sys.__stdout__
    # print(f"Processing complete. Output saved to {log_file}")
