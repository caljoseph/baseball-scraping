import json
import os
import time
import datetime
from pathlib import Path
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
import logging
from tqdm import tqdm

from csv_utils import initialize_csv
from game_state import Half, GameState, FieldPosition
from main import process_event
from scraper import setup_webdriver, process_box, process_summary
from statcast_at_bats import get_at_bat_summary_for_game







if __name__ == "__main__":
    # Example usage:
    # First, scrape all games
    scraper = GameScraper("urls/ohtani_games.csv")
    scraper.scrape_games()

    # Then process the scraped games
    # create_dataset(300, "urls/ohtani_games.csv")