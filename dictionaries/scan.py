import json
import string
import argparse

def find_filtered_positions(json_file, min_words):
    # Load the JSON data
    with open(json_file, 'r') as file:
        data = json.load(file)

    # Initialize a list to store results
    filtered_positions = []

    # Iterate through each letter from 'a' to 'z'
    for letter in string.ascii_lowercase:
        letter_data = data.get(letter, {})  # Get letter data or an empty dict if missing

        # Check all positions from 1 to 6
        for position in range(1, 7):
            words = letter_data.get(str(position), [])  # Positions are stored as strings in JSON

            # Check if the number of words is less than the specified minimum
            if len(words) < min_words:
                filtered_positions.append({'letter': letter, 'position': position, 'words': words})

    # Log total number of incomplete positions
    print(f"Total incomplete positions found: {len(filtered_positions)} (Min words required: {min_words})\n")

    # Print the results
    for entry in filtered_positions:
        print(f"Letter: {entry['letter']}, Position: {entry['position']}, Words: {entry['words']}")

    print(f"\n{len(filtered_positions)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Find letter positions with less than a specified number of words in a JSON file.')
    parser.add_argument('json_file', type=str, help='Path to the JSON file')
    parser.add_argument('min_words', type=int, nargs='?', default=3, help='Minimum required words count (default: 3)')
    args = parser.parse_args()

    find_filtered_positions(args.json_file, args.min_words)
