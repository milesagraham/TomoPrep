"""
Version Date : 14th October, 2024
Author : Miles Graham
Institution : University of Oxford / Diamond Light Source
Description: This script has a list of functions which are called in the execution script in order to enact tomography
preprocessing steps (soft linking relevant files, motion correcting movies, ctf estimation, stacking tilt series,
aligning tilt series) and then writing out the star files and soft linking the required files for relion import.
"""

import re
import os
import pandas as pd
import json
import subprocess
import time
import multiprocessing
import random

from functions import readmdoc
from functions import Color
from functions import print_colored
from functions import parse_config
from functions import get_position_name



'''
File sorter reads an mdoc and for all of the files listed under 'SubFramePath' will create a soft link under directories
with the position name. E.g. If processing a position labelled "Position_1_3", a directory will be created and all of 
the tilt movies relating to this position will be soft linked within this directory. 
'''

def file_sorter(mdoc_file, config):

    get_position_name(mdoc_file, config)
    position_prefix, position_directory = get_position_name(mdoc_file, config)
    mdoc_df = readmdoc(mdoc_file)
    mdoc_directory = config.get('mdoc_directory')

    # Create a directory for this position in the processing directory if it doesn't exist
    os.makedirs(position_directory, exist_ok=True)
    # Create symbolic links to the files listd in SubFramePath column in the newly made folder
    linked_files_count = 0  # Counter for linked files
    for _, row in mdoc_df.iterrows():
        subframe_path = row["SubFramePath"]
        if not pd.isnull(subframe_path):
            subframe_file = os.path.basename(subframe_path)
            source_path = os.path.join(mdoc_directory, subframe_file)
            link_path = os.path.join(position_directory, subframe_file)
            os.symlink(source_path, link_path)
            linked_files_count += 1


    print_colored(f'{position_prefix} : {linked_files_count} relevant files found.',
                      Color.GREEN)

    return position_prefix, position_directory


'''
rawtlt_maker makes the basic rawtlt files required for AreTomo tilt series alignment to describe the tilt scheme used.
This currently does not include any dose information for dose weighting and could potentially be added in future 
versions. 
'''


def rawtlt_maker(mdoc_file, config):

    # Generate mdoc DataFrame and use it to define the target prefix and folder path
    mdoc_df = readmdoc(mdoc_file)
    position_prefix, position_directory = get_position_name(mdoc_file, config)

    # Sort the DataFrame by the 'TiltAngle' column in ascending order (from most negative to positive)
    sorted_df = mdoc_df.sort_values(by='TiltAngle')

    # Extract the 'TiltAngle' and the 'ImageFile' information from the mdoc
    tilt_angles = sorted_df['TiltAngle']

    # Create a text file and write the sorted tilt angles to it
    rawtlt_file = f"{position_directory}/{position_prefix}.rawtlt"
    with open(rawtlt_file, 'w') as file:
        file.write(tilt_angles.to_string(index=False))
    print_colored(f'{position_prefix} : Tilt information written to {rawtlt_file}.', Color.GREEN)


'''
Newstacker creates the input file required for Imod's newstack. 
'''


def newstacker(mdoc_file, config):

    mdoc_df = readmdoc(mdoc_file)
    sorted_df = mdoc_df.sort_values(by='TiltAngle')
    position_prefix, position_directory = get_position_name(mdoc_file, config)

    file_type = config['file_type']

    # write out newstack input using the dataframe sorted according to tilt angle.
    output_file = f'{position_directory}/{position_prefix}_newstack.txt'

    with open(output_file, "w") as file:
        file.write(str(len(sorted_df)) + "\n")

        for _, row in sorted_df.iterrows():
            subframe_path = row["SubFramePath"]
            modified_path = subframe_path.replace(".", "_", 1)  # Replace only the first occurrence
            modified_path = modified_path.replace(".{}".format(file_type), ".mrc")

            file.write("MotionCorr/job002/" + modified_path + "\n")
            file.write("0\n")


'''
motioncorr feeds the parameters obtained from the readmdoc function and the configuration file (user input), in order 
to modify a template submission script with the desired parameters for RELION's implementation of MotionCor. 
'''


def motioncorr(mdoc_file, processing_directory):
    # extract relevant information from mdoc
    mdoc_df = readmdoc(mdoc_file)
    position_name = mdoc_df.loc[1, "ImageFile"]

    # Read the configuration file
    with open('config_TomoPrep.json', 'r') as f:
        config_data = f.read()

    # Parse the contents of the JSON file
    config = json.loads(config_data)
    file_type = config['file_type']

    # Remove the file extension from position name in order to get position prefix and its relevant processing directory.
    position_prefix = position_name.replace(".{}".format(file_type), "")
    position_directory = os.path.join(processing_directory, position_prefix)

    # Read the configuration file
    with open('config_TomoPrep.json', 'r') as f:
        config_data = f.read()

    # Parse the contents of the JSON file
    config = json.loads(config_data)

    # Extract the parameters required for the motion correction and newstack.

    relion_module = config['relion_module']
    imod_module = config['imod_module']
    MOTIONCORR_SLURM_TEMPLATE = config['MOTIONCORR_SLURM_TEMPLATE']
    file_type = config['file_type']
    pixel_size = config['pixel_size']
    partition = config['partition']
    MPIs = config['MPIs']
    threads = config['threads']
    Cs = config['Cs']
    Q0 = config['Q0']
    frame_dose = config['frame_dose']
    motioncorr_patches = config['motioncorr_patches']
    eer_grouping = config['eer_grouping']
    gainref = config['gainref']
    max_jobs = config['max_jobs']
    voltage = config['voltage']

    # Read the template file
    with open(MOTIONCORR_SLURM_TEMPLATE, "r") as f:
        slurm_template = f.read()
        slurm_script = slurm_template.format(processing_directory=processing_directory, relion_module=relion_module,
                                             imod_module=imod_module, partition=partition, MPIs=MPIs, threads=threads,
                                             position_directory=position_directory, pixel_size=pixel_size,
                                             voltage=voltage, Cs=Cs, Q0=Q0, file_type=file_type,
                                             position_prefix=position_prefix,
                                             frame_dose=frame_dose, motioncorr_patches=motioncorr_patches,
                                             eer_grouping=eer_grouping, gainref=gainref)
        slurm_script_path = f"motioncorr_slurm_{position_prefix}.sh"
        slurm_script_path = os.path.join(position_directory, slurm_script_path)
        # Write the modified SLURM script to a new file
        with open(slurm_script_path, "w") as f:
            f.write(slurm_script)

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
                print_colored(f"{position_prefix} : Motion Correction job submitted.",
                              Color.RED)
                break  # Exit the loop after submitting a job


'''
aretomo feeds the parameters obtained from the readmdoc function and the configuration file (user input), in order 
to modify a template submission script with the desired parameters for AreTomo (UCSF). 
'''


def aretomo(mdoc_file, processing_directory):
    # read the mdoc being processed and extract name of position (with file extension)
    mdoc_df = readmdoc(mdoc_file)
    position_name = mdoc_df.loc[1, "ImageFile"]

    # Read the configuration file
    with open('config_TomoPrep.json', 'r') as f:
        config_data = f.read()
    config = json.loads(config_data)

    # Remove the file extension from position name in order to get position prefix and its relevant processing directory.
    file_type = config['file_type']
    position_prefix = position_name.replace(".{}".format(file_type), "")
    position_directory = os.path.join(processing_directory, position_prefix)

    # extract the remaining relevant parameters required for the AreTomo job.
    ARETOMO_SLURM_TEMPLATE = config['ARETOMO_SLURM_TEMPLATE']
    partition = config['partition']
    MPIs = config['MPIs']
    threads = config['threads']
    aretomo_thickness = config['aretomo_thickness']
    aretomo_volume_binning = config['aretomo_volume_binning']
    aretomo_DarkTol = config['aretomo_DarkTol']
    aretomo_AliZ = config['aretomo_AliZ']
    aretomo_module = config['aretomo_module']
    max_jobs = config['max_jobs']

    # Read the template submission script file
    with open(ARETOMO_SLURM_TEMPLATE, "r") as f:
        slurm_template = f.read()
        slurm_script = slurm_template.format(aretomo_module=aretomo_module, partition=partition, MPIs=MPIs,
                                             aretomo_DarkTol=aretomo_DarkTol,
                                             aretomo_volume_binning=aretomo_volume_binning,
                                             threads=threads, aretomo_thickness=aretomo_thickness,
                                             position_directory=position_directory, aretomo_AliZ=aretomo_AliZ,
                                             position_prefix=position_prefix)
        slurm_script_path = f"aretomo_slurm_{position_prefix}.sh"
        slurm_script_path = os.path.join(position_directory, slurm_script_path)

        # Write the modified SLURM script to a new file
        with open(slurm_script_path, "w") as f:
            f.write(slurm_script)

        # pause until inputs are ready
        exit_success = f'{position_directory}/MotionCorr/job002/RELION_JOB_EXIT_SUCCESS'
        message_printed = False
        while not os.path.exists(exit_success):

            if not message_printed:
                print_colored(
                    f"{position_prefix} : AreTomo is waiting for motion corrected movies...",
                    Color.YELLOW)
                message_printed = True

        # pause to make sure stack has been made before submitting
        time.sleep(60)

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
                print_colored(f"{position_prefix} : AreTomo job submitted.",
                              Color.RED)
                break  # Exit the loop after submitting a job


'''
ctffind feeds the parameters obtained from the readmdoc function and the configuration file (user input), in order 
to modify a template submission script with the desired parameters for CtfFind4, run through RELION. 
'''


def ctffind(mdoc_file, processing_directory):
    # extract relevant information from mdoc
    mdoc_df = readmdoc(mdoc_file)
    position_name = mdoc_df.loc[1, "ImageFile"]

    # Read the configuration file
    with open('config_TomoPrep.json', 'r') as f:
        config_data = f.read()
    config = json.loads(config_data)

    # Remove the file extension from position name in order to get position prefix and its relevant processing directory.
    file_type = config['file_type']
    position_prefix = position_name.replace(".{}".format(file_type), "")
    position_directory = os.path.join(processing_directory, position_prefix)

    # extract the remaining relevant parameters required for the Ctffind job.
    CTFFIND_SLURM_TEMPLATE = config['CTFFIND_SLURM_TEMPLATE']
    pixel_size = config['pixel_size']
    partition = config['partition']
    ctffind_module = config['ctffind_module']
    Cs = config['Cs']
    Q0 = config['Q0']
    lowest_defocus_search = config['lowest_defocus_search']
    highest_defocus_search = config['highest_defocus_search']
    max_jobs = config['max_jobs']
    voltage = config['voltage']
    max_ctf_fit_resolution = config['max_ctf_fit_resolution']
    min_ctf_fit_resolution = config['min_ctf_fit_resolution']

    # convert the defocus units
    min_defocus_search = abs(lowest_defocus_search * 10000)
    max_defocus_search = abs(highest_defocus_search * 10000)

    # Read the template file
    with open(CTFFIND_SLURM_TEMPLATE, "r") as f:
        slurm_template = f.read()
        slurm_script = slurm_template.format(processing_directory=processing_directory, ctffind_module=ctffind_module,
                                             partition=partition, position_directory=position_directory,
                                             position_prefix=position_prefix, Cs=Cs, Q0=Q0,
                                             max_ctf_fit_resolution=max_ctf_fit_resolution,
                                             min_ctf_fit_resolution=min_ctf_fit_resolution,
                                             min_defocus_search=min_defocus_search,
                                             max_defocus_search=max_defocus_search, pixel_size=pixel_size,
                                             voltage=voltage)
        slurm_script_path = f"ctffind_slurm_{position_prefix}.sh"
        slurm_script_path = os.path.join(position_directory, slurm_script_path)
        # Write the modified SLURM script to a new file
        with open(slurm_script_path, "w") as f:
            f.write(slurm_script)

        # pause until inputs are ready

        exit_success = f'{position_directory}/MotionCorr/job002/RELION_JOB_EXIT_SUCCESS'
        message_printed = False
        while not os.path.exists(exit_success):
            if not message_printed:
                print_colored(
                    f"{position_prefix} : CtfFind is waiting for motion corrected movies...",
                    Color.YELLOW)
                message_printed = True
            time.sleep(10)  # Wait for 10 seconds before checking again

        # pause to make sure stack has been made before submitting
        time.sleep(60)

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
                print_colored(f"{position_prefix} : CtfFind job submitted.",
                              Color.RED)
                break  # Exit the loop after submitting a job


def tomo_order_list_maker(mdoc_file, processing_directory):
    # extract relevant information from mdoc
    mdoc_df = readmdoc(mdoc_file)
    position_name = mdoc_df.loc[1, "ImageFile"]

    # Read the configuration file
    with open('config_TomoPrep.json', 'r') as f:
        config_data = f.read()
    config = json.loads(config_data)

    # Remove the file extension from position name in order to get position prefix and its relevant processing directory.
    file_type = config['file_type']
    position_prefix = position_name.replace(".{}".format(file_type), "")
    position_directory = os.path.join(processing_directory, position_prefix)
    # stating the name/location of the csv file to be generated
    order_list_path = f"{position_prefix}_order_list.csv"
    order_list_path = os.path.join(position_directory, order_list_path)
    # saving tilt angles from unsorted dataframe
    tilt_angles = mdoc_df['TiltAngle']
    # Create a new DataFrame with two columns: Index and TiltAngle
    order_list_df = pd.DataFrame({
        "Index": range(1, len(tilt_angles) + 1),
        "TiltAngle": tilt_angles
    })
    # write out the order list file
    order_list_df.to_csv(order_list_path, index=False, header=False)


def relion_setup(mdoc_file, processing_directory):
    # extract relevant information from mdoc
    mdoc_df = readmdoc(mdoc_file)
    position_name = mdoc_df.loc[1, "ImageFile"]

    # Read the configuration file
    with open('config_TomoPrep.json', 'r') as f:
        config_data = f.read()
    config = json.loads(config_data)

    # Remove the file extension from position name in order to get position prefix and its relevant processing directory.
    file_type = config['file_type']
    position_prefix = position_name.replace(".{}".format(file_type), "")
    position_directory = os.path.join(processing_directory, position_prefix)

    # Make the RELION_PROCESSING directory and the position directories within the tomograms folder
    relion_processing_path = os.path.join(processing_directory, "RELION_PROCESSING")
    tomograms_directory = os.path.join(relion_processing_path, "tomograms")
    relion_position_directory = os.path.join(tomograms_directory, position_prefix)

    os.makedirs(relion_position_directory, exist_ok=True)

    # soft link in the unaligned stack
    unaligned_stack = f"{position_prefix}_unaligned.mrc"
    source_path = os.path.join(position_directory, unaligned_stack)

    message_printed = False
    while not os.path.exists(source_path):

        if not message_printed:
            print_colored(
                f"{position_prefix} : RELION is waiting for the unaligned stack...",
                Color.YELLOW)
            message_printed = True
        time.sleep(2)  # Wait for 10 seconds before checking again

    link_path = os.path.join(relion_position_directory, unaligned_stack)
    os.symlink(source_path, link_path)
    print_colored(f'{position_prefix} : {unaligned_stack} has been soft linked to the RELION processing directory.',
                  Color.GREEN)

    # soft link in the ctf file
    ctf_list = f"{position_prefix}.txt"
    ctf_directory = os.path.join(position_directory, "CTF")
    source_path = os.path.join(ctf_directory, ctf_list)

    message_printed = False
    while not os.path.exists(source_path):
        if not message_printed:
            print_colored(
                f"{position_prefix} : RELION is waiting for CTF files...",
                Color.YELLOW)
            message_printed = True
        time.sleep(2)  # Wait for 10 seconds before checking again

    link_path = os.path.join(relion_position_directory, ctf_list)
    os.symlink(source_path, link_path)
    print_colored(f'{position_prefix} : {ctf_list} has been soft linked to the RELION processing directory.',
                  Color.GREEN)

    # soft link in 'imod' files

    source_imod_directory = f"{processing_directory}/{position_prefix}/{position_prefix}_Imod"
    tiltcom_file = f"{source_imod_directory}/tilt.com"
    newstcom_file = f"{source_imod_directory}/newst.com"
    tlt_file = f"{source_imod_directory}/{position_prefix}.tlt"
    st_file = f"{source_imod_directory}/{position_prefix}.st"
    xf_file = f"{source_imod_directory}/{position_prefix}.xf"
    xtilt_file = f"{source_imod_directory}/{position_prefix}.xtilt"
    source_path = source_imod_directory
    message_printed = False
    while not os.path.exists(source_path) and os.path.exists(tiltcom_file) and os.path.exists(
        tlt_file) and os.path.exists(newstcom_file) and os.path.exists(xtilt_file) and os.path.exists(
        xf_file) and os.path.exists(st_file):
        if not message_printed:
            print_colored(
                f"{position_prefix} : RELION is waiting for IMOD files from AreTomo...",
                Color.YELLOW)
            message_printed = True

    for file in os.listdir(source_imod_directory):
        source_path = os.path.join(source_imod_directory, file)
        link_path = os.path.join(relion_position_directory, file)
        os.symlink(source_path, link_path)
        print_colored(f'{position_prefix} : {file} has been soft linked to the RELION processing directory.',
                      Color.GREEN)

    # soft link the order list
    order_list = f"{position_prefix}_order_list.csv"
    source_path = os.path.join(position_directory, order_list)
    link_path = os.path.join(relion_position_directory, order_list)

    message_printed = False
    while not os.path.exists(source_path):

        if not message_printed:
            print_colored(
                f"{position_prefix} : RELION is waiting for the Tomo Order List...",
                Color.YELLOW)
            message_printed = True
        time.sleep(2)  # Wait for 10 seconds before checking again

    os.symlink(source_path, link_path)
    print_colored(f'{position_prefix} : {order_list} has been soft linked to the RELION processing directory.',
                  Color.GREEN)

    # remove the extra line at the bottom of the .tlt file generated by AreTomo (ugh!)
    # dan says that the xf file also has a blank line - maybe worth looking at
    tlt_file_path = os.path.join(relion_position_directory, f"{position_prefix}.tlt")
    # Read the contents of the file
    with open(tlt_file_path, 'r') as file:
        lines = file.readlines()

    # Remove the trailing whitespace (including the extra blank line) if it exists
    lines = [line.rstrip() for line in lines]

    # Write the modified content back to the file
    with open(tlt_file_path, 'w') as file:
        file.write('\n'.join(lines))

    # modify the EXCLUDE list in the tilt.com file to match the RELION naming scheme.

    def increment_number(number):
        return str(int(number) + 1)

    def process_numbers(match):
        numbers = match.group(1).replace(',', ' ').split()
        incremented_numbers = ','.join(increment_number(num) for num in numbers)
        return f'EXCLUDELIST {incremented_numbers}'

    imod_directory = f"{processing_directory}/{position_prefix}/{position_prefix}_Imod"
    tilt_file = f"{imod_directory}/tilt.com"
    modified_tilt_file = f"{relion_position_directory}/tilt.com"

    with open(tilt_file, 'r') as file:
        content = file.read()

    pattern = r'EXCLUDELIST\s+(.*?)$'
    content = re.sub(pattern, process_numbers, content, flags=re.MULTILINE)

    # remove existing tilt file
    if os.path.exists(modified_tilt_file):
        os.remove(modified_tilt_file)

    with open(modified_tilt_file, 'w') as file:
        file.write(content)


class RelionStarFile:
    def __init__(self, file_path):
        self.file_path = file_path

    def write_header(self):
        star_header = """data_

loop_
_rlnTomoName
_rlnTomoTiltSeriesName
_rlnTomoImportCtfFindFile
_rlnTomoImportImodDir
_rlnTomoImportFractionalDose
_rlnTomoImportOrderList
_rlnTomoImportCulledFile

"""

        with open(self.file_path, 'w') as f:
            f.write(star_header)

    def write_line(self, tomo_name, tilt_series_path, ctf_file_path, relion_imod_directory, fractional_dose,
                   order_list_path, import_tomo_culled_file):
        with open(self.file_path, 'a') as f:
            f.write(
                f"{tomo_name}   {tilt_series_path}   {ctf_file_path}   {relion_imod_directory}   {fractional_dose}   {order_list_path}   {import_tomo_culled_file}\n")


def relion_import_star_maker(mdoc_file, processing_directory):
    # extract relevant information from mdoc
    mdoc_df = readmdoc(mdoc_file)
    position_name = mdoc_df.loc[1, "ImageFile"]
    number_of_frames = mdoc_df.loc[1, "NumSubFrames"]

    # Read the configuration file
    with open('config_TomoPrep.json', 'r') as f:
        config_data = f.read()
    config = json.loads(config_data)

    # Remove the file extension from position name in order to get position prefix and its relevant processing directory.
    file_type = config['file_type']
    position_prefix = position_name.replace(".{}".format(file_type), "")
    dose_per_frame = config['frame_dose']
    relion_processing_path = os.path.join(processing_directory, "RELION_PROCESSING")

    tomo_name = position_prefix
    tilt_series_path = f"tomograms/{position_prefix}/{position_prefix}.st"
    ctf_file_path = f"tomograms/{position_prefix}/{position_prefix}.txt"
    relion_imod_directory = f"tomograms/{position_prefix}"
    fractional_dose = number_of_frames * dose_per_frame
    order_list_path = f"tomograms/{position_prefix}/{position_prefix}_order_list.csv"
    import_tomo_culled_file = f"tomograms/{position_prefix}/{position_prefix}_culled_file.mrc"

    relion_star_file_path = os.path.join(relion_processing_path, "tomograms_descr.star")
    relion_star_file = RelionStarFile(relion_star_file_path)

    # If the STAR file doesn't exist, write the header first
    if not os.path.exists(relion_star_file_path):
        relion_star_file.write_header()

    # Call the write_line method for each entry
    relion_star_file.write_line(tomo_name, tilt_series_path, ctf_file_path, relion_imod_directory, fractional_dose,
                                order_list_path, import_tomo_culled_file)


def relion_import():
    # Read the configuration file
    with open('config_TomoPrep.json', 'r') as f:
        config_data = f.read()

    # Parse the contents of the JSON file
    config = json.loads(config_data)

    # Extract the parameters required for the motion correction and newstack.

    relion_module = config['relion_module']
    processing_directory = config['processing_directory']
    RELION_IMPORT_TEMPLATE = config['IMPORT_SLURM_TEMPLATE']
    pixel_size = config['pixel_size']
    partition = config['partition']
    Cs = config['Cs']
    Q0 = config['Q0']
    voltage = config['voltage']

    relion_directory = f"{processing_directory}/RELION_PROCESSING"
    # Read the template file
    with open(RELION_IMPORT_TEMPLATE, "r") as f:
        slurm_template = f.read()
        slurm_script = slurm_template.format(relion_module=relion_module, partition=partition,
                                             relion_directory=relion_directory, pixel_size=pixel_size,
                                             voltage=voltage, Cs=Cs, Q0=Q0)
        slurm_script_path = "relion_import.sh"
        slurm_script_path = os.path.join(relion_directory, slurm_script_path)
        # Write the modified SLURM script to a new file
        with open(slurm_script_path, "w") as f:
            f.write(slurm_script)
        print_colored("RELION Import Job Submitted", Color.RED)
        subprocess.run(['sbatch', slurm_script_path])


def relion_tomo_reconstruct(mdoc_file):
    # extract relevant information from mdoc
    mdoc_df = readmdoc(mdoc_file)
    position_name = mdoc_df.loc[1, "ImageFile"]

    # Read the configuration file
    with open('config_TomoPrep.json', 'r') as f:
        config_data = f.read()
    config = json.loads(config_data)

    # Remove the file extension from position name in order to get position prefix and its relevant processing directory.
    file_type = config['file_type']
    position_prefix = position_name.replace(".{}".format(file_type), "")
    position_directory = os.path.join(processing_directory, position_prefix)

    # extract the remaining relevant parameters required for the Ctffind job.
    TOMO_RECONSTRUCT_SLURM_TEMPLATE = config['TOMO_RECONSTRUCT_SLURM_TEMPLATE']
    partition = config['partition']
    relion_module = config['relion_module']
    relion_directory = f"{processing_directory}/RELION_PROCESSING"
    max_jobs = config['max_jobs']
    tomo_reconstruct_binning = config['tomo_reconstruct_binning']
    tomo_reconstruct_threads = config['tomo_reconstruct_threads']

    # Read the template file
    with open(TOMO_RECONSTRUCT_SLURM_TEMPLATE, "r") as f:
        slurm_template = f.read()
        slurm_script = slurm_template.format(relion_module=relion_module, partition=partition,
                                             tomo_reconstruct_threads=tomo_reconstruct_threads,
                                             position_directory=position_directory,
                                             tomo_reconstruct_binning=tomo_reconstruct_binning,
                                             relion_directory=relion_directory, position_prefix=position_prefix)
        slurm_script_path = f"relion_tomo_reconstruct_{position_prefix}.sh"
        slurm_script_path = os.path.join(position_directory, slurm_script_path)
        # Write the modified SLURM script to a new file
        with open(slurm_script_path, "w") as f:
            f.write(slurm_script)

        exit_success = f'{relion_directory}/ImportTomo/job001/RELION_JOB_EXIT_SUCCESS'

        message_printed = False
        while not os.path.exists(exit_success):
            if not message_printed:
                print_colored(
                    f"{position_prefix} : Waiting for import to finish...",
                    Color.YELLOW)
                message_printed = True
            time.sleep(10)  # Wait for 10 seconds before checking again

        print(f"{position_prefix} : Import finished. Requesting tomogram reconstruction in RELION")

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
                print_colored(f"{position_prefix} : RELION reconstruct tomogram job submitted.",
                              Color.RED)
                break  # Exit the loop after submitting a job


def process_mdoc_file(mdoc_file):
    try:
        # Read the configuration file
        with open('config_TomoPrep.json', 'r') as f:
            config_data = f.read()

        # Parse the contents of the JSON file
        config = json.loads(config_data)
        processing_directory = config["processing_directory"]
        mdoc_directory = config["mdoc_directory"]
        mdoc_absolute_path = os.path.join(mdoc_directory, mdoc_file)
        file_sorting = config["file_sorting"]
        motion_correction = config["motion_correction"]
        ctf_estimation = config["ctf_estimation"]
        aretomo_alignment = config["aretomo_alignment"]
        relion_tomo_import = config['relion_tomo_import']

        if file_sorting == "YES":
            # Call functions with error handling
            file_sorter(mdoc_absolute_path, config)
            rawtlt_maker(mdoc_absolute_path, config)
            newstacker(mdoc_absolute_path, config)
            tomo_order_list_maker(mdoc_absolute_path, processing_directory)
        if motion_correction == "YES":
            motioncorr(mdoc_absolute_path, processing_directory)
        if aretomo_alignment == "YES":
            aretomo(mdoc_absolute_path, processing_directory)
        if ctf_estimation == "YES":
            ctffind(mdoc_absolute_path, processing_directory)
    except Exception as e:
        print(f"An error occurred during processing: {e}")


if __name__ == '__main__':
    # Read the configuration file
    with open('config_TomoPrep.json', 'r') as f:
        config_data = f.read()

    # Parse the contents of the JSON file
    config = json.loads(config_data)
    processing_directory = config["processing_directory"]
    mdoc_directory = config["mdoc_directory"]
    relion_tomogram_reconstruction = config["relion_tomogram_reconstruction"]
    relion_tomo_import = config['relion_tomo_import']

    # Get a list of all mdoc files in the directory
    mdoc_files = [filename for filename in os.listdir(mdoc_directory) if
                  filename.endswith(".mdoc") and "_override" not in filename]

    # Create a separate process for each mdoc file
    processes = []
    for mdoc_file in mdoc_files:
        sleep_time = random.randint(1, 5)
        time.sleep(sleep_time)
        p = multiprocessing.Process(target=process_mdoc_file, args=(mdoc_file,))
        processes.append(p)
        p.start()

    # Wait for all processes to complete
    for p in processes:
        p.join()

    if relion_tomo_import == "YES":
        for mdoc_file in mdoc_files:
            mdoc_absolute_path = os.path.join(mdoc_directory, mdoc_file)
            relion_setup(mdoc_absolute_path, processing_directory)
            relion_import_star_maker(mdoc_absolute_path, processing_directory)
        relion_import()

    if relion_tomogram_reconstruction == "YES":
        for mdoc_file in mdoc_files:
            mdoc_absolute_path = os.path.join(mdoc_directory, mdoc_file)
            relion_tomo_reconstruct(mdoc_absolute_path)

    print("All jobs submitted. Check for their completion!")
