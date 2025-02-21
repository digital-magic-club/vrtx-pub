import json
import random
import logging
from collections import defaultdict, OrderedDict
import unidecode
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

def remove_similar_words(words):
    """Remove similar words that differ only by the last letter (e.g., plural forms)"""
    cleaned_words = {}
    for word in words:
        # Normalize the word by removing accents and special characters
        root = unidecode.unidecode(word).lower()
        # If the word ends with 's' and the word without the 's' exists, skip it
        if root.endswith('s') and root[:-1] in cleaned_words:
            continue
        cleaned_words[root] = word
    return list(cleaned_words.values())

def main():
    # Check if a file is provided as parameter
    if len(sys.argv) < 2:
        print('Usage: python script.py <file_path> [--verbose]')
        sys.exit(1)

    file_path = sys.argv[1]
    verbose = '--verbose' in sys.argv

    # The structure stores, for each letter and letter position, two sets:
    # one for normal words and one for low-priority words.
    words_dict = defaultdict(lambda: defaultdict(lambda: {"normal": set(), "low": set()}))

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            total_lines = len(lines)

            for idx, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # Determine priority: if the line ends with "!", mark as low priority.
                if line.endswith('!'):
                    priority = "low"
                    # Remove the exclamation mark (it should not appear in the final export)
                    line = line[:-1].rstrip()
                else:
                    priority = "normal"

                # Normalize the word
                normalized_word = unidecode.unidecode(line)
                # Filter to keep only alphabetical characters (for letter/position assignment)
                filtered_word = ''.join(char for char in normalized_word if char.isalpha())

                # For each letter (positions 1 to 6 only)
                for index, letter in enumerate(filtered_word):
                    letter = letter.lower()
                    position = index + 1
                    if 1 <= position <= 6:
                        group = words_dict[letter][position]
                        if priority == "normal":
                            group["normal"].add(normalized_word)
                            # If this word was already in low priority, remove it.
                            group["low"].discard(normalized_word)
                        else:  # priority == "low"
                            # Only add as low priority if not already present as normal.
                            if normalized_word not in group["normal"]:
                                group["low"].add(normalized_word)

                # Log progress if verbose mode is enabled
                if verbose:
                    progress_percentage = (idx + 1) / total_lines * 100
                    logging.info(f'Processing line {idx + 1}/{total_lines} - {progress_percentage:.2f}% complete')

        # Build the final output structure
        output_data = OrderedDict()
        for letter in sorted(words_dict):
            output_data[letter] = OrderedDict()
            for pos in sorted(words_dict[letter]):
                group = words_dict[letter][pos]

                # Run the similar-word removal on each category
                normal_list = remove_similar_words(list(group["normal"]))
                low_list = remove_similar_words(list(group["low"]))

                # Final selection: always use normal words first
                final_words = []
                if len(normal_list) >= 5:
                    # Enough normal words: select 5 random ones
                    final_words = random.sample(normal_list, 5)
                else:
                    # Use all normal words, in random order
                    normal_order = normal_list.copy()
                    random.shuffle(normal_order)
                    final_words = normal_order
                    needed = 5 - len(final_words)
                    if low_list:
                        # If more than needed, select randomly; otherwise, take them all.
                        additional = random.sample(low_list, needed) if len(low_list) > needed else low_list.copy()
                        random.shuffle(additional)
                        # Append the low-priority words AFTER the normal words.
                        final_words.extend(additional)

                output_data[letter][pos] = final_words

        # Write the result into a JSON file
        with open('result.json', 'w', encoding='utf-8') as json_file:
            json.dump(output_data, json_file, ensure_ascii=False, indent=3)

    except FileNotFoundError:
        print(f'Error: The file "{file_path}" was not found.')
        sys.exit(1)

if __name__ == '__main__':
    main()
