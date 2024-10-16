import csv
from game_state import FieldPosition

def initialize_csv(filename):
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = [
            "Event_Type", "Is_Decision", "Inning", "Half", "At_Bat", "Score_Deficit", "Outs",
            "First_Base", "Second_Base", "Third_Base",
            "Home_Pitcher", "Away_Pitcher"
        ]
        # Add individual lineup positions
        for i in range(1, 10):
            fieldnames.extend([f"Home_Lineup_{i}"])
        for i in range(1, 10):
            fieldnames.extend([f"Away_Lineup_{i}"])
        # Add position players
        fieldnames.extend([f"Home_{pos.name}" for pos in FieldPosition] + [f"Away_{pos.name}" for pos in FieldPosition])

        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

def write_decision_point_to_csv(filename, decision_point):
    with open(filename, 'a', newline='') as csvfile:
        fieldnames = [
            "Event_Type", "Is_Decision", "Inning", "Half", "At_Bat", "Score_Deficit", "Outs",
            "First_Base", "Second_Base", "Third_Base",
            "Home_Pitcher", "Away_Pitcher"
        ]
        # Add individual lineup positions
        for i in range(1, 10):
            fieldnames.extend([f"Home_Lineup_{i}"])
        for i in range(1, 10):
            fieldnames.extend([f"Away_Lineup_{i}"])
        # Add position players
        fieldnames.extend([f"Home_{pos.name}" for pos in FieldPosition] + [f"Away_{pos.name}" for pos in FieldPosition])

        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        row = {
            "Event_Type": decision_point["Event_Type"]["type"],
            "Is_Decision": decision_point["Is_Decision"],
            "Inning": decision_point["Inning"],
            "Half": decision_point["Half"].name,
            "At_Bat": decision_point["At_Bat"],
            "Score_Deficit": decision_point["Score_Deficit"],
            "Outs": decision_point["Outs"],
            "First_Base": decision_point["BasesOccupied"]["First_Base"],
            "Second_Base": decision_point["BasesOccupied"]["Second_Base"],
            "Third_Base": decision_point["BasesOccupied"]["Third_Base"],
            "Home_Pitcher": decision_point["Home_Pitcher"],
            "Away_Pitcher": decision_point["Away_Pitcher"],
        }

        # Add individual lineup positions
        for i in range(1, 10):
            row[f"Home_Lineup_{i}"] = decision_point[f"Home_Lineup_{i}"]

        # Add individual lineup positions
        for i in range(1, 10):
            row[f"Away_Lineup_{i}"] = decision_point[f"Away_Lineup_{i}"]

        # Add position players
        for pos in FieldPosition:
            row[f"Home_{pos.name}"] = decision_point["HomePositionPlayers"][pos]
            row[f"Away_{pos.name}"] = decision_point["AwayPositionPlayers"][pos]

        writer.writerow(row)