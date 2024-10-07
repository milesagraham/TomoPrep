#!/bin/bash
#SBATCH --job-name=IMPORT
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=20
#SBATCH --output={relion_directory}/import_out.txt
#SBATCH --error={relion_directory}/import_err.txt
#SBATCH --open-mode=append
#SBATCH --partition={partition}
#SBATCH --mem-per-cpu=7G

# Print the exact command into the output file for debugging and to log the
# exact RELION version

echo "------------------------------------------------------------------------------------"

module purge
module load {relion_module}
cd {relion_directory}
mkdir Import
mkdir Import/job001
relion_tomo_import_tomograms --i tomograms_descr.star --o ImportTomo/job001/tomograms.star --angpix {pixel_size} --voltage {voltage} --Cs {Cs} --Q0 {Q0} --flipYZ --flipZ --pipeline_control ImportTomo/job001/

echo "------------------------------------------------------------------------------------"

