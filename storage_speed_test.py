import os
import time
import logging
import platform
import subprocess
import psutil
import npyscreen
from tqdm import tqdm

# Setup logger
logger = logging.getLogger('speed_test_logger')
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('./logs/info.log')
error_handler = logging.FileHandler('./logs/error.log')
file_handler.setLevel(logging.INFO)
error_handler.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
error_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(error_handler)

# Function to measure write speed with a progress bar
def write_speed_test(device_path, size_in_mb=500):
    file_path = os.path.join(device_path, 'speed_test_file')
    data = os.urandom(1024 * 1024)  # 1MB chunk of random data

    start_time = time.time()
    try:
        with open(file_path, 'wb') as f:
            for _ in tqdm(range(size_in_mb), desc="Writing file", unit="MB"):
                f.write(data)  # Write in chunks of 1MB
        end_time = time.time()

        write_time = end_time - start_time
        write_speed = size_in_mb / write_time  # MB per second
        logger.info(f"Write speed on {device_path}: {write_speed:.2f} MB/s")
        os.remove(file_path)  # Clean up the test file
        return write_speed
    except Exception as e:
        logger.error(f"Error in write_speed_test: {e}")
        raise

# Function to measure read speed with a progress bar
def read_speed_test(device_path, size_in_mb=500):
    file_path = os.path.join(device_path, 'speed_test_file')
    data = os.urandom(1024 * 1024)  # 1MB chunk to write first

    # Write the file first to read it back
    with open(file_path, 'wb') as f:
        for _ in range(size_in_mb):
            f.write(data)

    start_time = time.time()
    try:
        with open(file_path, 'rb') as f:
            for _ in tqdm(range(size_in_mb), desc="Reading file", unit="MB"):
                f.read(1024 * 1024)  # Read in 1MB chunks
        end_time = time.time()

        read_time = end_time - start_time
        read_speed = size_in_mb / read_time  # MB per second
        logger.info(f"Read speed on {device_path}: {read_speed:.2f} MB/s")
        os.remove(file_path)  # Clean up the test file
        return read_speed
    except Exception as e:
        logger.error(f"Error in read_speed_test: {e}")
        raise

# Function to detect available devices on Linux with detailed info
def get_linux_devices():
    try:
        devices = []
        result = subprocess.run(['lsblk', '-o', 'NAME,SIZE,FSTYPE,MOUNTPOINT'], stdout=subprocess.PIPE, text=True)
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) == 4 and parts[3]:  # Only get devices with a mount point
                name, size, fstype, mountpoint = parts
                devices.append((f"{name} ({size}, {fstype})", mountpoint))
        return devices
    except Exception as e:
        logger.error(f"Error detecting devices on Linux: {e}")
        return []

# Function to detect available devices on Windows
def get_windows_devices():
    try:
        devices = []
        partitions = psutil.disk_partitions()
        for partition in partitions:
            devices.append((f"{partition.device} ({partition.fstype})", partition.mountpoint))
        return devices
    except Exception as e:
        logger.error(f"Error detecting devices on Windows: {e}")
        return []

# Function to detect available devices on macOS
def get_macos_devices():
    try:
        devices = []
        result = subprocess.run(['diskutil', 'list'], stdout=subprocess.PIPE, text=True)
        lines = result.stdout.splitlines()
        for line in lines:
            if '/dev/disk' in line:
                parts = line.split()
                if len(parts) >= 2:
                    device = parts[0]
                    mountpoint = parts[-1] if len(parts) > 2 else ''
                    devices.append((device, mountpoint))
        return devices
    except Exception as e:
        logger.error(f"Error detecting devices on macOS: {e}")
        return []

# Function to get available devices based on OS
def get_available_devices():
    system = platform.system()
    if system == 'Linux':
        return get_linux_devices()
    elif system == 'Windows':
        return get_windows_devices()
    elif system == 'Darwin':  # macOS
        return get_macos_devices()
    else:
        logger.error('Unsupported operating system')
        return []

# Terminal GUI using npyscreen
class SpeedTestApp(npyscreen.NPSAppManaged):
    def onStart(self):
        self.addForm('MAIN', MainForm, name='Storage Speed Tester')

class MainForm(npyscreen.Form):
    def create(self):
        # Dynamically fetch available devices
        self.devices = get_available_devices()
        self.device_names = [f"{d[0]} ({d[1]})" for d in self.devices]

        self.device_selector = self.add(npyscreen.TitleSelectOne, max_height=4, value=[0], name="Select a device",
                                        values=self.device_names, scroll_exit=True)
        self.file_size = self.add(npyscreen.TitleText, name="File size (MB)", value="500")
        self.speed_test_button = self.add(npyscreen.ButtonPress, name="Run Speed Test")
        self.speed_test_button.whenPressed = self.run_speed_test

        # Add Exit button to safely terminate the program
        self.exit_button = self.add(npyscreen.ButtonPress, name="Exit")
        self.exit_button.whenPressed = self.exit_program

        self.result_display = self.add(npyscreen.MultiLineEdit, max_height=10, editable=False)

    def run_speed_test(self):
        self.result_display.value = "Running speed tests...\n"
        self.result_display.display()

        selected_index = self.device_selector.value[0]
        device_name, device_path = self.devices[selected_index]
        file_size_mb = int(self.file_size.value)

        try:
            write_speed = write_speed_test(device_path, size_in_mb=file_size_mb)
            read_speed = read_speed_test(device_path, size_in_mb=file_size_mb)
            result_text = f"{device_name} - Write Speed: {write_speed:.2f} MB/s, Read Speed: {read_speed:.2f} MB/s"
            self.result_display.value = result_text
            self.result_display.display()
        except Exception as e:
            self.result_display.value = f"Error occurred: {str(e)}"
            self.result_display.display()

    def exit_program(self):
        try:
            # Optionally, terminate pending operations if applicable
            self.terminate_pending_operations()
            npyscreen.notify_wait("Exiting the program... All pending operations have been terminated.")
            logger.info("Program exited successfully. No pending operations.")
            self.parentApp.switchForm(None)  # This exits the npyscreen application
        except Exception as e:
            logger.error(f"Error while exiting: {e}")
            npyscreen.notify_confirm(f"An error occurred while exiting: {e}", title="Error")

    def terminate_pending_operations(self):
        global terminate_flag
        terminate_flag = True  # Set the flag to stop operations
        logger.info("Terminate flag set, stopping pending operations...")



if __name__ == '__main__':
    app = SpeedTestApp().run()
