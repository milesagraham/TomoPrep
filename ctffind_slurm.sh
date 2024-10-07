#!/bin/bash
#SBATCH --job-name=ctf_estimation
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output={position_directory}/ctffind_{position_prefix}_out.txt
#SBATCH --error={position_directory}/ctffind_{position_prefix}_err.txt
#SBATCH --open-mode=append
#SBATCH --partition={partition}
#SBATCH --mem-per-cpu=7G

# Print the exact command into the output file for debugging and to log the exact RELION version

module purge
module load {ctffind_module}

echo "------------------------------------------------------------------------------------"

cd {position_directory}
mkdir CTF

ctffind <<EOF
{position_prefix}_unaligned.mrc
no
CTF/{position_prefix}.ctf
{pixel_size}
{voltage}
{Cs}
{Q0}
512
{min_ctf_fit_resolution}
{max_ctf_fit_resolution}
{min_defocus_search}
{max_defocus_search}
100.0
no
no
no
no
no
EOF

echo "------------------------------------------------------------------------------------"

