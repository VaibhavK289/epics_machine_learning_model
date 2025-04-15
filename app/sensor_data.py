import pandas as pd
import numpy as np
from datetime import datetime
import os
import json
import matplotlib.pyplot as plt

# Remove the model import for now and implement fallback behavior
# from model import predict_failure

# Create data directory if it doesn't exist
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

def process_sensor_data(data):
    """
    Process raw sensor data and check for anomalies.
    
    Args:
        data (dict): Raw sensor data with temperature, vibration, pressure, rpm
        
    Returns:
        dict: Processed data with anomaly flags and derived features
    """
    # Extract values
    temperature = float(data.get('temperature', 0))
    vibration = float(data.get('vibration', 0))
    pressure = float(data.get('pressure', 0))
    rpm = float(data.get('rpm', 0))
    machine_id = data.get('machine_id', 'unknown')
    
    # Add timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Calculate derived features
    vibration_to_rpm_ratio = vibration / max(rpm, 1)  # Avoid division by zero
    temperature_pressure_ratio = temperature / max(pressure, 0.1)  # Avoid division by zero
    
    # Define normal operating ranges
    temp_normal = (50, 90)
    vibration_normal = (0.1, 5.0)
    pressure_normal = (0.8, 1.2)
    rpm_normal = (1000, 3000)
    
    # Check for anomalies
    temp_anomaly = temperature < temp_normal[0] or temperature > temp_normal[1]
    vibration_anomaly = vibration < vibration_normal[0] or vibration > vibration_normal[1]
    pressure_anomaly = pressure < pressure_normal[0] or pressure > pressure_normal[1]
    rpm_anomaly = rpm < rpm_normal[0] or rpm > rpm_normal[1]
    
    # Overall anomaly status
    anomaly_detected = temp_anomaly or vibration_anomaly or pressure_anomaly or rpm_anomaly
    
    # Create processed data dictionary
    processed_data = {
        'timestamp': timestamp,
        'machine_id': machine_id,
        'temperature': temperature,
        'vibration': vibration,
        'pressure': pressure,
        'rpm': rpm,
        'vibration_to_rpm_ratio': vibration_to_rpm_ratio,
        'temperature_pressure_ratio': temperature_pressure_ratio,
        'temp_anomaly': temp_anomaly,
        'vibration_anomaly': vibration_anomaly,
        'pressure_anomaly': pressure_anomaly,
        'rpm_anomaly': rpm_anomaly,
        'anomaly_detected': anomaly_detected
    }
    
    # Add simple rule-based failure prediction since model module is not available
    if anomaly_detected:
        # Simple rule-based failure prediction as fallback
        failure_probability = 0.0
        failure_type = "Unknown"
        
        if temp_anomaly and temperature > temp_normal[1]:
            failure_probability += 0.3
            failure_type = "Overheating"
        
        if vibration_anomaly and vibration > vibration_normal[1]:
            failure_probability += 0.4
            failure_type = "Bearing Failure" if failure_type == "Unknown" else failure_type
        
        if pressure_anomaly:
            failure_probability += 0.2
            failure_type = "Pressure Issue" if failure_type == "Unknown" else failure_type
        
        if rpm_anomaly:
            failure_probability += 0.1
            failure_type = "Motor Issue" if failure_type == "Unknown" else failure_type
        
        processed_data['failure_probability'] = min(failure_probability, 0.95)  # Cap at 95%
        processed_data['failure_type'] = failure_type
    
    return processed_data

def store_data(processed_data):
    """
    Store processed sensor data to CSV and update alert database if anomaly detected.
    
    Args:
        processed_data (dict): Processed sensor data
        
    Returns:
        bool: Success status
    """
    try:
        # Create filename with machine ID
        machine_id = processed_data.get('machine_id', 'unknown')
        csv_file = os.path.join(DATA_DIR, f"{machine_id}_sensor_data.csv")
        
        # Convert to DataFrame for easier handling
        df = pd.DataFrame([processed_data])
        
        # Check if file exists to determine if header is needed
        file_exists = os.path.isfile(csv_file)
        
        # Append to CSV file
        df.to_csv(csv_file, mode='a', header=not file_exists, index=False)
        
        # If anomaly detected, store in alerts file
        if processed_data.get('anomaly_detected', False):
            alert_file = os.path.join(DATA_DIR, f"{machine_id}_alerts.csv")
            alert_exists = os.path.isfile(alert_file)
            df.to_csv(alert_file, mode='a', header=not alert_exists, index=False)
            
            # Also create a JSON alert for immediate notification
            alert_json = os.path.join(DATA_DIR, f"{machine_id}_latest_alert.json")
            with open(alert_json, 'w') as f:
                json.dump(processed_data, f, indent=2)
        
        return True
    
    except Exception as e:
        print(f"Error storing data: {e}")
        return False

def get_historical_data(machine_id, days=7):
    """
    Retrieve historical sensor data for analysis.
    
    Args:
        machine_id (str): Machine identifier
        days (int): Number of days of data to retrieve
        
    Returns:
        DataFrame: Historical sensor data
    """
    csv_file = os.path.join(DATA_DIR, f"{machine_id}_sensor_data.csv")
    
    if not os.path.isfile(csv_file):
        print(f"No data file found for machine {machine_id}")
        return pd.DataFrame()
    
    try:
        # Read the CSV file
        df = pd.read_csv(csv_file)
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter for the requested time period
        cutoff_date = datetime.now() - pd.Timedelta(days=days)
        recent_data = df[df['timestamp'] >= cutoff_date]
        
        return recent_data
    
    except Exception as e:
        print(f"Error retrieving historical data: {e}")
        return pd.DataFrame()

def generate_sensor_report(machine_id):
    """
    Generate a report of sensor readings and anomalies.
    
    Args:
        machine_id (str): Machine identifier
        
    Returns:
        dict: Report data with statistics and charts
    """
    # Get recent data
    df = get_historical_data(machine_id)
    
    if df.empty:
        return {"error": "No data available for report generation"}
    
    # Calculate basic statistics
    stats = {
        'total_readings': len(df),
        'anomaly_count': df['anomaly_detected'].sum(),
        'anomaly_percentage': round(100 * df['anomaly_detected'].sum() / len(df), 2),
        'avg_temperature': round(df['temperature'].mean(), 2),
        'max_temperature': round(df['temperature'].max(), 2),
        'avg_vibration': round(df['vibration'].mean(), 2),
        'max_vibration': round(df['vibration'].max(), 2),
        'last_reading_time': df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Create plots directory if it doesn't exist
    plots_dir = os.path.join(DATA_DIR, 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    
    # Generate temperature trend chart
    plt.figure(figsize=(10, 6))
    plt.plot(df['timestamp'], df['temperature'], 'r-')
    plt.title(f'Temperature Trend - Machine {machine_id}')
    plt.xlabel('Time')
    plt.ylabel('Temperature (°C)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    temp_chart_path = os.path.join(plots_dir, f'{machine_id}_temp_trend.png')
    plt.savefig(temp_chart_path)
    plt.close()
    
    # Generate vibration trend chart
    plt.figure(figsize=(10, 6))
    plt.plot(df['timestamp'], df['vibration'], 'b-')
    plt.title(f'Vibration Trend - Machine {machine_id}')
    plt.xlabel('Time')
    plt.ylabel('Vibration')
    plt.xticks(rotation=45)
    plt.tight_layout()
    vibration_chart_path = os.path.join(plots_dir, f'{machine_id}_vibration_trend.png')
    plt.savefig(vibration_chart_path)
    plt.close()
    
    # Return report data
    report = {
        'machine_id': machine_id,
        'stats': stats,
        'charts': {
            'temperature_chart': temp_chart_path,
            'vibration_chart': vibration_chart_path
        }
    }
    
    return report