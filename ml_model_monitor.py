#!/usr/bin/env python3
# ml_model_monitor.py

import os
import time
import json
import hashlib
import logging
import pandas as pd
from datetime import datetime
import subprocess
import smtplib
from email.message import EmailMessage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('model_monitor.log'),
        logging.StreamHandler()
    ]
)

class ModelMonitor:
    def __init__(self, 
                 container_name,
                 csv_path,
                 check_interval=300,  # 5 minutes
                 backup_dir='./csv_backups',
                 metrics_dir='./metrics',
                 alert_email=None):
        
        self.container_name = container_name
        self.csv_path = csv_path
        self.check_interval = check_interval
        self.backup_dir = backup_dir
        self.metrics_dir = metrics_dir
        self.alert_email = alert_email
        
        # Create directories if they don't exist
        os.makedirs(backup_dir, exist_ok=True)
        os.makedirs(metrics_dir, exist_ok=True)
        
        # Initialize with current state
        self.last_hash = self._get_file_hash()
        self.last_check_time = datetime.now()
        self._backup_current_csv()
        
        logging.info(f"Started monitoring for CSV: {csv_path}")
        logging.info(f"Container: {container_name}")
    
    def _get_file_hash(self):
        """Generate MD5 hash of the CSV file"""
        try:
            with open(self.csv_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logging.error(f"Error hashing file: {e}")
            return None
    
    def _get_container_stats(self):
        """Get Docker container resource usage"""
        try:
            result = subprocess.run(
                ['docker', 'stats', self.container_name, '--no-stream', '--format', '{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}'],
                capture_output=True, text=True, check=True
            )
            cpu, mem_usage, mem_perc = result.stdout.strip().split(',')
            return {
                'cpu_percentage': cpu.strip(),
                'memory_usage': mem_usage.strip(),
                'memory_percentage': mem_perc.strip()
            }
        except Exception as e:
            logging.error(f"Error getting container stats: {e}")
            return None
    
    def _backup_current_csv(self):
        """Create a backup of the current CSV file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"{os.path.basename(self.csv_path)}.{timestamp}")
        try:
            df = pd.read_csv(self.csv_path)
            df.to_csv(backup_path, index=False)
            logging.info(f"Created backup at {backup_path}")
            return backup_path
        except Exception as e:
            logging.error(f"Error creating backup: {e}")
            return None
    
    def _compare_csv_changes(self, previous_path):
        """Compare current CSV with previous backup and analyze changes"""
        try:
            current_df = pd.read_csv(self.csv_path)
            previous_df = pd.read_csv(previous_path)
            
            # Basic change statistics
            stats = {
                'current_rows': len(current_df),
                'previous_rows': len(previous_df),
                'rows_changed': abs(len(current_df) - len(previous_df)),
                'timestamp': datetime.now().isoformat()
            }
            
            # Column statistics (for numeric columns)
            col_stats = {}
            for col in current_df.select_dtypes(include=['number']).columns:
                if col in previous_df.columns:
                    col_stats[col] = {
                        'current_mean': current_df[col].mean(),
                        'previous_mean': previous_df[col].mean(),
                        'current_std': current_df[col].std(),
                        'previous_std': previous_df[col].std()
                    }
            
            stats['column_stats'] = col_stats
            return stats
        except Exception as e:
            logging.error(f"Error comparing CSVs: {e}")
            return None
    
    def _save_metrics(self, metrics):
        """Save metrics to JSON file"""
        if not metrics:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_path = os.path.join(self.metrics_dir, f"metrics_{timestamp}.json")
        
        try:
            with open(metrics_path, 'w') as f:
                json.dump(metrics, f, indent=2)
            logging.info(f"Saved metrics to {metrics_path}")
        except Exception as e:
            logging.error(f"Error saving metrics: {e}")
    
    def _send_alert(self, subject, message):
        """Send email alert if configured"""
        if not self.alert_email:
            return
            
        try:
            msg = EmailMessage()
            msg.set_content(message)
            msg['Subject'] = subject
            msg['From'] = 'ml_monitor@example.com'
            msg['To'] = self.alert_email
            
            # Configure your SMTP settings here
            smtp_server = 'smtp.example.com'
            smtp_port = 587
            smtp_user = 'your_username'
            smtp_password = 'your_password'
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
                
            logging.info(f"Sent alert email to {self.alert_email}")
        except Exception as e:
            logging.error(f"Error sending alert: {e}")
    
    def check_for_changes(self):
        """Check for changes in the monitored CSV file"""
        current_hash = self._get_file_hash()
        
        if current_hash and current_hash != self.last_hash:
            logging.info(f"Changes detected in {self.csv_path}")
            
            # Backup current state
            backup_path = self._backup_current_csv()
            
            # Get last backup before the change
            backups = sorted([f for f in os.listdir(self.backup_dir) 
                             if f.startswith(os.path.basename(self.csv_path))])
            
            if len(backups) >= 2:
                previous_backup = os.path.join(self.backup_dir, backups[-2])
                
                # Compare changes
                changes = self._compare_csv_changes(previous_backup)
                
                if changes:
                    # Save metrics
                    container_stats = self._get_container_stats()
                    if container_stats:
                        changes['container_stats'] = container_stats
                    
                    self._save_metrics(changes)
                    
                    # Check for significant changes that require alerts
                    if changes.get('rows_changed', 0) > 1000:  # Example alert threshold
                        self._send_alert(
                            "ML Model Alert: Significant CSV Changes", 
                            f"Detected {changes['rows_changed']} row changes in {self.csv_path}"
                        )
            
            self.last_hash = current_hash
        
        self.last_check_time = datetime.now()
    
    def run_monitor_loop(self):
        """Main monitoring loop"""
        try:
            while True:
                self.check_for_changes()
                logging.info(f"Next check in {self.check_interval} seconds")
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logging.info("Monitoring stopped by user")
        except Exception as e:
            logging.error(f"Error in monitoring loop: {e}")


if __name__ == "__main__":
    # Configure these parameters for your setup
    monitor = ModelMonitor(
        container_name="busy_haslett",
        csv_path="C:/Epics-ML_model-deploy/app/data",
        check_interval=10,  # Check every 5 minutes
        backup_dir="./csv_backups",
        metrics_dir="./metrics",
        alert_email="vaibhavkrkandhway@gmail.com"  # Optional, set to None to disable alerts
    )
    
    # Start monitoring
    monitor.run_monitor_loop()