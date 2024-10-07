#!/bin/bash
#SBATCH --job-name=tomo_reconstruct
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=10
#SBATCH --output={position_directory}/tomo_reconstruct_{position_prefix}_out.txt
#SBATCH --error={position_directory}/tomo_reconstruct_{position_prefix}_err.txt
#SBATCH --open-mode=append
#SBATCH --partition={partition}
#SBATCH --mem-per-cpu=7G

# Print the exact command into the output file for debugging and to log the
# exact RELION version

echo "------------------------------------------------------------------------------------"

module purge
module load {relion_module}
cd {relion_directory}
mkdir volumes
relion_tomo_reconstruct_tomogram --t ImportTomo/job001/tomograms.star --tn {position_prefix} --bin {tomo_reconstruct_binning} --noctf --j {tomo_reconstruct_threads} --o volumes/{position_prefix}_relion_volume.mrc

echo "------------------------------------------------------------------------------------"

