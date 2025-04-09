import json
import pandas as pd
from pathlib import Path

def load_scenarios():
    """Load the coordination data from JSON file."""
    data_path = Path(__file__).parent.parent.parent / 'data' / 'raw' / 'data_coordination.json'
    with open(data_path, 'r') as f:
        data = json.load(f)
    return data

def get_available_scenarios(data):
    """Get list of available scenarios."""
    return list(data.keys())

def display_scenario_data(data, scenario):
    """Display data for a specific scenario."""
    if scenario not in data:
        print(f"Scenario '{scenario}' not found!")
        return None
    
    scenario_data = data[scenario]
    df = pd.DataFrame(scenario_data)
    return df

def main():
    # Load the data
    data = load_scenarios()
    
    # Get available scenarios
    scenarios = get_available_scenarios(data)
    print("\nAvailable scenarios:")
    for i, scenario in enumerate(scenarios, 1):
        print(f"{i}. {scenario}")
    
    # Get user input
    while True:
        try:
            choice = input("\nEnter the number of the scenario to display (or 'q' to quit): ")
            if choice.lower() == 'q':
                break
            
            choice = int(choice)
            if 1 <= choice <= len(scenarios):
                scenario = scenarios[choice - 1]
                df = display_scenario_data(data, scenario)
                if df is not None:
                    print(f"\nData for scenario '{scenario}':")
                    print(df)
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number or 'q' to quit.")

if __name__ == "__main__":
    main() 