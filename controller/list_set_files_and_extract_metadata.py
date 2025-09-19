import os
from db_utils import extract_setfile_metadata

# Set the directory containing .set files
SET_FILE_DIR = r"C:\Users\Administrator\Documents\GitHub\PocketFlowProject\set_file_library\01_user_inputs"

def main():
    # List all .set files in the directory
    set_files = [
        f for f in os.listdir(SET_FILE_DIR)
        if f.lower().endswith('.set') and os.path.isfile(os.path.join(SET_FILE_DIR, f))
    ]
    
    if not set_files:
        print("No .set files found in the directory.")
        return

    print(f"Found {len(set_files)} .set files:\n")
    
    for set_file in set_files:
        set_file_path = os.path.join(SET_FILE_DIR, set_file)
        try:
            metadata = extract_setfile_metadata(set_file_path)
        except Exception as e:
            metadata = {"error": str(e)}
        
        print(f"{set_file}:")
        for k, v in metadata.items():
            print(f"  {k}: {v}")
        print("-" * 40)

if __name__ == "__main__":
    main()