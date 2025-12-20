import sys
import pandas as pd

def process_stream():
    """
    Reads binary-decoded log lines from stdin and outputs aggregate CSV.
    """
    data = []
    
    # Reading from Standard Input (piped from C tool)
    for line in sys.stdin.buffer:
        try:
            parts = line.decode('utf-8', errors='ignore').strip().split()
            if len(parts) < 4:
                continue

            # FIFA 98 Format: timestamp, clientID, objectID, size, method, status, type
            timestamp = float(parts[0])
            size_bytes = int(parts[3])
            
            data.append({
                'timestamp': timestamp,
                'bytes': size_bytes
            })
        except Exception:
            continue

    if not data:
        print("No data processed!")
        return

    df = pd.DataFrame(data)
    
    # Convert timestamp to DateTime
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('datetime', inplace=True)
    
    # AGGREGATION FOR THESIS:
    # Resample to 1-minute intervals to visualize the Load/Burst
    # calculating Request Count (Load) and Total Bandwidth
    resampled = df.resample('1T').agg({
        'bytes': ['count', 'sum']
    })
    
    resampled.columns = ['request_count', 'total_bytes']
    
    # Save to the mounted volume
    output_file = "/data/processed_workload.csv"
    resampled.to_csv(output_file)
    print(f"Success! Processed data saved to {output_file}")

if __name__ == "__main__":
    process_stream()
