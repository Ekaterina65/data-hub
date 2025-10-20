import csv
from typing import List, Dict, Tuple, Optional

def validate_csv(
    filepath: str,
    expected_columns: List[str],
    column_types: Optional[Dict[str, type]] = None
) -> Tuple[bool, List[str]]:
    """
    Validates a CSV file against expected columns and data types.

    This function checks for the presence of required columns in the header
    and validates the data types of specified columns for each row.

    Args:
        filepath: Path to the CSV file.
        expected_columns: A list of column names expected in the header.
        column_types: A dictionary mapping column names to their expected types
                      (e.g., {'age': int, 'score': float}).

    Returns:
        A tuple containing:
        - bool: True if the file is valid, False otherwise.
        - list[str]: A list of human-readable error messages.
    """
    errors = []
    column_types = column_types or {}

    try:
        with open(filepath, mode='r', encoding='utf-8', newline='') as csvfile:
            reader = csv.reader(csvfile)

            try:
                header = next(reader)
            except StopIteration:
                return False, ["CSV file is empty or contains only a header."]

            # 1. Validate header columns
            header_set = set(header)
            missing_columns = set(expected_columns) - header_set
            if missing_columns:
                errors.append(f"Missing columns in CSV header: {', '.join(sorted(list(missing_columns)))}")
                # Stop validation if headers are incorrect, as subsequent checks will fail.
                return False, errors

            header_map = {name: i for i, name in enumerate(header)}

            # 2. Validate data rows
            for row_num, row in enumerate(reader, start=2):
                if len(row) != len(header):
                    errors.append(f"Row {row_num}: Mismatched number of columns. Expected {len(header)}, found {len(row)}.")
                    continue

                for col_name, expected_type in column_types.items():
                    col_index = header_map[col_name]
                    value = row[col_index]

                    if not value.strip() and expected_type is not str:
                        # Allow empty values for non-string types, assuming they represent NULL.
                        # Add specific logic here if empty strings should be an error.
                        continue

                    try:
                        # Perform type casting to validate
                        expected_type(value)
                    except (ValueError, TypeError):
                        errors.append(
                            f"Row {row_num}, Column '{col_name}': Value '{value}' cannot be cast to {expected_type.__name__}."
                        )

    except FileNotFoundError:
        return False, [f"File not found at path: {filepath}"]
    except Exception as e:
        return False, [f"An unexpected error occurred: {str(e)}"]

    is_valid = not bool(errors)
    return is_valid, errors
