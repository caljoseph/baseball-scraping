from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import unidecode
import time
import re
from event_handlers import remove_middle_initials


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        print(f'{method.__name__} took {te - ts:.2f} seconds')
        return result

    return timed


@timeit
def setup_webdriver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chromedriver_path = "/usr/local/bin/chromedriver"
    service = Service(chromedriver_path)
    return webdriver.Chrome(service=service, options=chrome_options)


@timeit
def get_lineup_subs_and_mapping(driver, team_class):
    lineup = []
    sub_ins = []
    player_id_map = {}
    position_map = {}
    try:
        ts = time.time()
        table = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f".{team_class} .batters tbody"))
        )
        te = time.time()
        print(f'  Waiting for table took {te - ts:.2f} seconds')

        ts = time.time()
        rows = table.find_elements(By.TAG_NAME, "tr")[:-1]
        te = time.time()
        print(f'  Finding table rows took {te - ts:.2f} seconds')

        ts = time.time()
        for row in rows:
            player_cell = row.find_element(By.CSS_SELECTOR, "td:first-child")
            player_link = player_cell.find_element(By.CSS_SELECTOR, "a[href^='https://www.mlb.com/player/']")
            player_id = int(player_link.get_attribute('href').split('/')[-1])
            player_name = unidecode.unidecode(player_link.get_attribute('aria-label'))

            player_id_map[player_id] = remove_middle_initials(player_name)
            is_sub = 'SubstitutePlayerWrapper' in player_cell.get_attribute('innerHTML')

            position = driver.execute_script("""
                var row = arguments[0];
                var positionSpan = row.querySelector('span[data-mlb-test="boxscoreTeamTablePlayerPosition"]');
                if (positionSpan) {
                    var fullPosition = positionSpan.textContent.trim();
                    return fullPosition.split('-')[0]; // Return only the first position
                }
                return '';
            """, row)

            position_map[player_id] = position if position else "Unknown"

            if is_sub:
                sub_ins.append(player_id)
            elif len(lineup) < 9:
                lineup.append(player_id)
        te = time.time()
        print(f'  Processing rows took {te - ts:.2f} seconds')

    except Exception as e:
        print(f"An error occurred while getting the lineup, substitutions, and player mapping: {e}")

    return lineup, sub_ins, player_id_map, position_map


@timeit
def get_bullpen_and_mapping(driver, team_class):
    bullpen = []
    pitcher_id_map = {}
    try:
        ts = time.time()
        table = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f".{team_class} .pitchers tbody"))
        )
        te = time.time()
        print(f'  Waiting for table took {te - ts:.2f} seconds')

        ts = time.time()
        rows = table.find_elements(By.TAG_NAME, "tr")[:-1]  # Exclude the last row (totals)
        te = time.time()
        print(f'  Finding table rows took {te - ts:.2f} seconds')

        ts = time.time()
        for row in rows:
            pitcher_cell = row.find_element(By.CSS_SELECTOR, "td:first-child")
            pitcher_link = pitcher_cell.find_element(By.CSS_SELECTOR, "a[href^='https://www.mlb.com/player/']")
            pitcher_id = int(pitcher_link.get_attribute('href').split('/')[-1])
            pitcher_name = unidecode.unidecode(pitcher_link.get_attribute('aria-label'))

            bullpen.append(pitcher_id)
            pitcher_id_map[pitcher_id] = pitcher_name
        te = time.time()
        print(f'  Processing rows took {te - ts:.2f} seconds')

    except Exception as e:
        print(f"An error occurred while getting the bullpen information: {e}")

    return bullpen, pitcher_id_map



@timeit
def process_box(driver, box_url):
    print("processing box for: ", box_url)
    ts_total = time.time()

    ts = time.time()
    driver.set_page_load_timeout(2)
    try:
        driver.get(box_url)
    except TimeoutException:
        print("Initial page load timed out, attempting to continue anyway")
    te = time.time()
    print(f'  Loading box page took {te - ts:.2f} seconds')

    # Wait for a key element that indicates the page is interactive
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".away-r1"))
        )
    except TimeoutException:
        print("Timed out waiting for key element, some data may be missing")

    results = {}
    for team in ['away', 'home']:
        ts = time.time()
        try:
            lineup, sub_ins, batter_map, position_map = get_lineup_subs_and_mapping(driver, f"{team}-r1")
            results[f'{team}_lineup'] = lineup
            results[f'{team}_sub_ins'] = sub_ins
            results[f'{team}_batter_map'] = batter_map
            results[f'{team}_position_map'] = position_map
        except Exception as e:
            print(f"Error processing {team} lineup: {e}")
        te = time.time()
        print(f'  Processing {team} team lineup took {te - ts:.2f} seconds')

        ts = time.time()
        try:
            bullpen, pitcher_map = get_bullpen_and_mapping(driver, f"{team}-r4")
            results[f'{team}_bullpen'] = bullpen
            results[f'{team}_pitcher_map'] = pitcher_map
        except Exception as e:
            print(f"Error processing {team} bullpen: {e}")
        te = time.time()
        print(f'  Processing {team} team bullpen took {te - ts:.2f} seconds')

        # Combine batter and pitcher maps
        results[f'{team}_player_map'] = {**results.get(f'{team}_batter_map', {}), **results.get(f'{team}_pitcher_map', {})}

    te_total = time.time()
    print(f'  Total processing time: {te_total - ts_total:.2f} seconds')

    return (
        results.get('away_lineup', []), results.get('away_sub_ins', []), results.get('away_player_map', {}),
        results.get('away_bullpen', []), results.get('away_position_map', {}),
        results.get('home_lineup', []), results.get('home_sub_ins', []), results.get('home_player_map', {}),
        results.get('home_bullpen', []), results.get('home_position_map', {})
    )


@timeit
def process_summary(driver, summary_url, home_abbr, away_abbr):
    ts_total = time.time()

    # Set a short page load timeout and attempt to load the summary page
    ts = time.time()
    driver.set_page_load_timeout(2)
    try:
        driver.get(summary_url)
    except TimeoutException:
        print("Initial page load timed out, attempting to continue anyway")
    te = time.time()
    print(f'  Loading summary page took {te - ts:.2f} seconds')

    # Wait for a key element that indicates the page is interactive
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class, 'PlayFeedstyle__InningHeader')]")
            )
        )
    except TimeoutException:
        print("Timed out waiting for key element, some data may be missing")

    game_summary = []
    current_inning = None

    ts = time.time()
    try:
        # Locate all relevant event elements
        events = driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'PlayFeedstyle__InningHeader') or "
            "contains(@class, 'SummaryPlaystyle__SummaryPlayWrapper')]"
        )
        te = time.time()
        print(f'  Finding all events took {te - ts:.2f} seconds')

        ts = time.time()
        for event in events:
            classes = event.get_attribute('class')
            if 'PlayFeedstyle__InningHeader' in classes:
                # Extract and store inning information
                inning = event.text.strip()
                game_summary.append({"inning": inning, "events": []})
                current_inning = inning
            else:
                try:
                    # Extract all event details within this wrapper
                    sub_events = event.find_elements(
                        By.XPATH,
                        ".//div[contains(@class, 'SummaryPlayEventsstyle__SummaryPlayEventsWrapper')]"
                    )

                    for sub_event in sub_events:
                        event_types = sub_event.find_elements(
                            By.XPATH,
                            ".//div[contains(@class, 'PlayActionstyle__PlayActionEvent')]"
                        )
                        event_descriptions = sub_event.find_elements(
                            By.XPATH,
                            ".//div[contains(@class, 'PlayActionstyle__PlayActionDescription')]"
                        )
                        score_updates = sub_event.find_elements(
                            By.XPATH,
                            ".//div[contains(@class, 'PlayScoresstyle__TeamScoresWrapper')]"
                        )

                        for event_type, event_description in zip(event_types, event_descriptions):
                            event_type_text = event_type.text.strip()
                            event_description_text = event_description.text.strip()

                            # Extract the atbat index
                            atbat_index = event_type.get_attribute('data-atbat-index')
                            if atbat_index is None:
                                atbat_index = event_description.get_attribute('data-atbat-index')

                            if atbat_index is not None:
                                try:
                                    atbat_index = int(atbat_index) + 1  # 0 index -> 1 index
                                except ValueError:
                                    print(f"      Invalid atbat-index value: {atbat_index}")
                                    atbat_index = None
                            else:
                                print("      No atbat-index found for this event.")

                            # Process score updates
                            score_update = None
                            if score_updates:
                                try:
                                    score_update = {
                                        away_abbr: int(score_updates[0].text.split(',')[0].split()[-1]),
                                        home_abbr: int(score_updates[1].text.split()[-1])
                                    }
                                except (IndexError, ValueError) as e:
                                    print(f"      Error parsing score updates: {e}")

                            # Process outs updates
                            outs_update = None
                            try:
                                outs_element = event_description.find_element(
                                    By.XPATH,
                                    ".//div[contains(@class, 'SummaryPlayEventsstyle__OutsWrapper')]"
                                )
                                if outs_element and outs_element.text.strip():
                                    try:
                                        outs_update = int(outs_element.text.strip().split()[0])
                                    except ValueError:
                                        print(
                                            f"      Error parsing outs updates for event: {event_type_text} - {event_description_text}")
                            except Exception as e:
                                print(f"      No outs element found or error: {e}")

                            # Handle offensive substitutions specifically
                            if "Offensive Substitution:" in event_description_text:
                                # Use regex to extract all 'Offensive Substitution: <desc>' parts
                                substitution_pattern = r'Offensive Substitution:\s*(.*?)\.?(?=\s*Offensive Substitution:|$)'
                                substitutions = re.findall(substitution_pattern, event_description_text, re.IGNORECASE | re.DOTALL)
                                print(f"      Found {len(substitutions)} offensive substitution(s)")

                                for idx, sub_desc in enumerate(substitutions):
                                    sub_desc = sub_desc.strip()
                                    detailed_description = f"Offensive Substitution: {sub_desc}"
                                    print(f"        Processing substitution {idx+1}: {detailed_description}")

                                    event_entry = {
                                        "type": "Offensive Substitution",
                                        "description": detailed_description,
                                        "score_update": score_update,
                                        "outs_update": outs_update,
                                        "atbat_index": atbat_index
                                    }

                                    # Append the event to the current inning's events
                                    if current_inning and game_summary:
                                        game_summary[-1]["events"].append(event_entry)
                                    else:
                                        print(
                                            f"      Skipped event due to no current inning: Offensive Substitution - {sub_desc}")
                            elif "Defensive Substitution:" in event_description_text:
                                # Use regex to extract all 'Defensive Substitution: <desc>' parts
                                substitution_pattern = r'Defensive Substitution:\s*(.*?)\.?(?=\s*Defensive Substitution:|$)'
                                substitutions = re.findall(substitution_pattern, event_description_text, re.IGNORECASE | re.DOTALL)
                                print(f"      Found {len(substitutions)} defensive substitution(s)")

                                for idx, sub_desc in enumerate(substitutions):
                                    sub_desc = sub_desc.strip()
                                    detailed_description = f"Defensive Substitution: {sub_desc}"
                                    print(f"        Processing substitution {idx+1}: {detailed_description}")

                                    event_entry = {
                                        "type": "Defensive Sub",
                                        "description": detailed_description,
                                        "score_update": score_update,
                                        "outs_update": outs_update,
                                        "atbat_index": atbat_index
                                    }

                                    # Append the event to the current inning's events
                                    if current_inning and game_summary:
                                        game_summary[-1]["events"].append(event_entry)
                                    else:
                                        print(
                                            f"      Skipped event due to no current inning: Defensive Substitution - {sub_desc}")

                            else:
                                event_entry = {
                                    "type": event_type_text,
                                    "description": event_description_text,
                                    "score_update": score_update,
                                    "outs_update": outs_update,
                                    "atbat_index": atbat_index
                                }

                                # Append the event to the current inning's events
                                if current_inning and game_summary:
                                    game_summary[-1]["events"].append(event_entry)
                                else:
                                    print(
                                        f"      Skipped event due to no current inning: {event_type_text} - {event_description_text}")

                except Exception as e:
                    print(f"    Error processing sub_event: {e}")
        te = time.time()
        print(f'  Processing all events took {te - ts:.2f} seconds')
    except Exception as e:
        print(f"Error finding or processing events: {e}")

    te_total = time.time()
    print(f'  Total processing time: {te_total - ts_total:.2f} seconds')

    return game_summary
