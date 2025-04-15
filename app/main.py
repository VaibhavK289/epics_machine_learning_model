#!/usr/bin/env python3
"""
Main entry point for the predictive maintenance application.
Coordinates between sensor data collection and the ML model.
"""

import os
import time
import queue
import threading
import csv
import signal
import sys
from datetime import datetime
import pandas as pd
from pycaret.classification import load_model, predict_model

# Import custom modules
from sensor_connector import ArduinoConnector, generate_mock_data
from sensor_data import process_sensor_data, store_data

# Global variables
data_queue = queue.Queue()
stop_event = threading.Event()
csv_file = None
writer = None

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    print("\nShutting down gracefully...")
    stop_event.set()
    
    # Close CSV file if open
    global csv_file
    if csv_file and not csv_file.closed:
        csv_file.close()
        
    sys.exit(0)

def setup_csv():
    """Set up the CSV file with headers."""
    os.makedirs('data', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"data/sensor_data_{timestamp}.csv"
    
    global csv_file, writer
    csv_file = open(file_path, "w", newline='')
    writer = csv.writer(csv_file)
    writer.writerow([
        "Type_H", "Type_L", "Type_M", "Tool wear", "rotation_speed", 
        "torque", "air_temp", "process_temp", "temp_diff", "Power", 
        "prediction_label", "prediction_score"
    ])
    
    return file_path

def data_processing_loop(model):
    """Process sensor data and make predictions."""
    while not stop_event.is_set():
        try:
            # Get data with timeout to allow checking stop_event
            try:
                data = data_queue.get(timeout=1)
            except queue.Empty:
                continue
                
            # Process data and make prediction
            processed_data = process_sensor_data(data, model)
            
            # Store results
            if csv_file and not csv_file.closed:
                store_data(processed_data, csv_file)
                csv_file.flush()  # Flush to disk immediately
                
            # Print prediction if failure detected
            if processed_data["prediction_label"] == 1:
                print(f"⚠️ FAILURE PREDICTED! Score: {processed_data['prediction_score']:.4f}")
            else:
                print(f"Normal operation. Score: {processed_data['prediction_score']:.4f}")
                
            data_queue.task_done()
        except Exception as e:
            print(f"Error in data processing: {e}")

def main():
    """Main application entry point."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting predictive maintenance system...")
    
    # Load the model
    try:
        model = load_model('predictive_maintenance')
        print("✅ Model loaded successfully")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return
    
    # Set up CSV file
    csv_path = setup_csv()
    print(f"✅ Data will be saved to: {csv_path}")
    
    # Start data processing thread
    processing_thread = threading.Thread(
        target=data_processing_loop, 
        args=(model,)
    )
    processing_thread.daemon = True
    processing_thread.start()
    
    # Start sensor data collection
    use_mock = os.environ.get('USE_MOCK_DATA', 'false').lower() == 'true'
    
    if use_mock:
        print("📊 Using mock sensor data (Arduino not connected)")
        sensor_thread = threading.Thread(
            target=generate_mock_data,
            args=(data_queue,)
        )
        sensor_thread.daemon = True
        sensor_thread.start()
    else:
        print("🔌 Connecting to Arduino sensor...")
        arduino_port = os.environ.get('ARDUINO_PORT', '/dev/ttyACM0')
        arduino = ArduinoConnector(port=arduino_port, data_queue=data_queue)
        
        # Try to connect to Arduino
        if not arduino.connect():
            print("⚠️ Could not connect to Arduino, falling back to mock data")
            sensor_thread = threading.Thread(
                target=generate_mock_data,
                args=(data_queue,)
            )
            sensor_thread.daemon = True
            sensor_thread.start()
        else:
            arduino.start()
    
    # Keep main thread alive
    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    
if __name__ == "__main__":
    main()