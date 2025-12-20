import sys
import gzip
import struct
import pandas as pd
import datetime
import os

# FIFA 98 Binary Format Structure
# uint32, uint32, uint32, uint32, uint8, uint8, uint8, uint8
STRUCT_FMT = '>IIIIBBBB'
STRUCT_SIZE = struct.calcsize(STRUCT_FMT)

# HARDCODED OUTPUT DIRECTORY -> MAPS TO WINDOWS DESKTOP
OUTPUT_DIR = "/data"

def parse_fifa_log(filepath):
    print(f"Processing: {filepath}")
    
    data = []
    
    try:
        with gzip.open(filepath, 'rb') as f:
            while True:
                chunk = f.read(STRUCT_SIZE)
                if not chunk:
                    break
                timestamp, clientID, objectID, size, method, status, type_, server = struct.unpack(STRUCT_FMT, chunk)
                data.append({
                    'timestamp': timestamp, 'clientID': clientID, 'objectID': objectID,
                    'size': size, 'method': method, 'status': status, 'type': type_, 'server': server
                })
                
    except FileNotFoundError:
        print("Error: File not found.")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    df = pd.DataFrame(data)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    
    print("\n--- DATA LOADED SUCCESSFULLY ---")
    print(f"Total Requests: {len(df)}")
    print("\nFirst 5 Rows:")
    print(df.head().to_string())

    # --- DETERMINE OUTPUT FILENAMES ---
    # Get just the filename (e.g., "test_log.gz") without the full folder path
    filename_only = os.path.basename(filepath)
    # Remove extension (e.g., "test_log")
    base_name = os.path.splitext(filename_only)[0]
    
    # FORCE SAVE TO /data (Windows Folder)
    csv_output = os.path.join(OUTPUT_DIR, base_name + ".csv")
    burst_output = os.path.join(OUTPUT_DIR, base_name + "_bursts.csv")

    # --- 1. SAVE FULL DATASET ---
    print(f"\nSaving full dataset to: {csv_output} ...")
    df.to_csv(csv_output, index=False)

    # --- 2. SAVE BURST ANALYSIS ---
    requests_per_min = df.set_index('datetime').resample('1min').size()
    print("\nBurst Analysis (Requests per Minute):")
    print(requests_per_min.head().to_string())

    print(f"\nSaving burst analysis to: {burst_output} ...")
    requests_per_min.to_csv(burst_output, header=['request_count'])

    print("--- DONE ---")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 /data/direct_parser.py <path_to_gz_file>")
    else:
        parse_fifa_log(sys.argv[1])
