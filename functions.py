import re
import os
import pandas as pd
import json
import subprocess
import time
import multiprocessing
import random


# ANSI escape codes for colors
class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'


def print_colored(message, color):
    print(f"{color}{message}{Color.RESET}")

'''
The readmdoc function extracts information from mdoc files produced by Tomography 5 (TFS) and stores within a pandas 
dataframe.
'''

def readmdoc(mdoc_file):
    # Read the mdoc file
    with open(mdoc_file, "r") as file:
        mdoc_content = file.read()

    # Extract the Voltage value from the header
    voltage_match = re.search(r"Voltage = (\d+\.\d+)", mdoc_content)
    if voltage_match:
        voltage = float(voltage_match.group(1))
    else:
        voltage = None

    # Extract the TiltAxisAngle value from the header
    tilt_axis_angle_match = re.search(r"TiltAxisAngle = ([-+]?\d+\.\d+)", mdoc_content)
    if tilt_axis_angle_match:
        tilt_axis_angle = float(tilt_axis_angle_match.group(1))
    else:
        tilt_axis_angle = None

    # Extract the ImageFile value from the header and remove the mrc extension
    image_file_match = re.search(r"ImageFile = (.+)", mdoc_content)
    if image_file_match:
        image_file = image_file_match.group(1).strip()
        image_file = image_file.replace(".mrc", "")
    else:
        image_file = None

    # Split the mdoc content into Z groups
    z_groups_raw = re.split(r"\[ZValue = (-?\d+)]", mdoc_content)
    z_groups = z_groups_raw[1:]  # Skip the first empty element

    # Extract the data for each Z group
    data = []
    for i in range(0, len(z_groups), 2):
        z_data = z_groups[i + 1]
        tilt_angle = re.search(r"TiltAngle = ([-+]?\d+\.\d+)", z_data).group(1)
        subframe_path = re.search(r"SubFramePath = (.+)", z_data).group(1).strip()
        subframe_path = re.search(r"[^\\/:*?\"<>|\r\n]+$", subframe_path).group()
        number_of_frames = re.search(r"NumSubFrames = (\d+)", z_data).group(1)

        # Read the configuration file
        with open('config_TomoPrep.json', 'r') as f:
            config_data = f.read()
        # Parse the contents of the JSON file
        config = json.loads(config_data)
        modify_subframe_path = config['modify_subframe_path']

        # Check if modification is needed
        if modify_subframe_path == "YES":
            # Replace "Fractions.mrc" with "fractions.mrc" in subframe_path
            subframe_path = subframe_path.replace("_Fractions.", "_fractions.")

        data.append((float(tilt_angle), subframe_path, float(number_of_frames)))

    # Create a pandas DataFrame
    mdoc_df = pd.DataFrame(data, columns=["TiltAngle", "SubFramePath", "NumSubFrames"])

    # Add the header information to each DataFrame entry
    mdoc_df["Voltage"] = voltage
    mdoc_df["TiltAxisAngle"] = tilt_axis_angle
    mdoc_df['ImageFile'] = image_file
    return mdoc_df


def parse_config(config_file):
    # Read the configuration file
    with open(config_file, 'r') as f:
        config_data = f.read()

    # Parse the contents of the JSON file
    config = json.loads(config_data)
    return config

def get_position_name(mdoc_file, config):
    # Read mdoc and config file to get key variables
    mdoc_df = readmdoc(mdoc_file)
    position_name = mdoc_df.loc[1, "ImageFile"]
    file_type = config.get('file_type')
    processing_directory = config.get('processing_directory')

    # extract the position name and directory
    position_prefix = position_name.replace(".{}".format(file_type), "")
    position_directory = os.path.join(processing_directory, position_prefix)
    return position_prefix, position_directory

def queue_submit(position_prefix, job_name, slurm_script_path, config):

    max_jobs = config['max_jobs']
    message_printed = False
    while True:
        # Run the squeue command to get the job count for the current user
        squeue_command = "squeue -u $(whoami) | wc -l"
        job_count = int(subprocess.check_output(squeue_command, shell=True).decode().strip())

        if job_count >= max_jobs:
            if not message_printed:
                print_colored(
                    f"{position_prefix} : Maximum number of SLURM jobs running ({job_count}). Waiting for the queue to go down...",
                    Color.YELLOW)
                message_printed = True
            sleep_time = random.randint(1, 10)
            time.sleep(sleep_time)
        else:
            # Submit a new job using sbatch
            subprocess.run(['sbatch', slurm_script_path])
            print_colored(f"{position_prefix} : {job_name} job submitted.",
                          Color.RED)
            break  # Exit the loop after submitting a job