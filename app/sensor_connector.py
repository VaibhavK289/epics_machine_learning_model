import serial
import time
import json
import queue
import threading
from datetime import datetime
import os

class ArduinoConnector:
    def __init__(self, port='/dev/ttyACM0', baudrate=9600, data_queue=None):
        """
        Initialize the Arduino connector.
        
        Args:
            port (str): Serial port (default for Arduino Uno on Linux)
            baudrate (int): Communication speed
            data_queue (Queue): Queue to send data to the processing script
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.connected = False
        self.data_queue = data_queue
        self.running = False
        
    def connect(self):
        """Attempt to connect to the Arduino."""
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Allow time for Arduino to reset
            self.connected = True
            print(f"Connected to Arduino on {self.port}")
            return True
        except serial.SerialException as e:
            print(f"Failed to connect to Arduino: {e}")
            return False
            
    def read_data(self):
        """Read data from Arduino and add to queue."""
        self.running = True
        while self.running:
            if not self.connected:
                if not self.connect():
                    print("Waiting to reconnect to Arduino...")
                    time.sleep(5)
                    continue
            
            try:
                if self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    try:
                        # Parse JSON data from Arduino
                        sensor_data = json.loads(line)
                        
                        # Add timestamp
                        sensor_data["timestamp"] = time.time()
                        
                        # Add to processing queue
                        if self.data_queue:
                            self.data_queue.put(sensor_data)
                            print(f"Data received: {sensor_data}")
                    except json.JSONDecodeError:
                        print(f"Invalid data received: {line}")
            except serial.SerialException as e:
                print(f"Serial connection error: {e}")
                self.connected = False
                if self.serial_conn:
                    self.serial_conn.close()
            
            time.sleep(0.1)
    
    def start(self):
        """Start reading from Arduino in a separate thread."""
        self.thread = threading.Thread(target=self.read_data)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        """Stop the reading thread and close connection."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        if self.serial_conn:
            self.serial_conn.close()
            self.connected = False

# Fallback to generate mock data if Arduino is not connected
def generate_mock_data(data_queue):
    """Generate mock sensor data similar to what Arduino would provide."""
    import random
    
    while True:
        data = {
            "tool_wear": random.randint(0, 300),
            "air_temp": random.randint(290, 310),
            "process_temp": random.randint(290, 330),
            "rotation_speed": random.randint(1000, 3000),
            "torque": random.randint(5, 75),
            "timestamp": time.time()
        }
        
        # Calculate derived values
        data["temp_diff"] = data["process_temp"] - data["air_temp"]
        data["power"] = 2 * 3.14159 * data["rotation_speed"] * data["torque"] / 60
        
        data_queue.put(data)
        time.sleep(0.5)

# Simple testing code
if __name__ == "__main__":
    test_queue = queue.Queue()
    
    try:
        arduino = ArduinoConnector(data_queue=test_queue)
        arduino.start()
        
        # Run for 30 seconds
        start_time = time.time()
        while time.time() - start_time < 30:
            if not test_queue.empty():
                data = test_queue.get()
                print(f"Received: {data}")
            time.sleep(0.1)
            
        arduino.stop()
    except KeyboardInterrupt:
        print("Test stopped by user")