#!/bin/bash

## Script by MG, Zhang Lab, STRUBI, Oxford, 15th April, 2023. Template submission script for AreTomo. Used by tomography preprocessing script.


### SLURM cluster settings####

#SBATCH --job-name=ARETOMO
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=10
#SBATCH --output={position_directory}/aretomo_{position_prefix}.out
#SBATCH --open-mode=append
#SBATCH --partition={partition}
#SBATCH --gres=gpu:1
#SBATCH --distribution=cyclic
#SBATCH --mem=30G

#change this line to the relevant module you want to load.

module purge
module load {aretomo_module}

# Print the exact command into the output file for debugging and to log the exact AreTomo version
echo "Path to the compiled ARETOMO version is: `which AreTomo`"

echo "------------------------------------------------------------------------------------"

#Below are the commands to be executed. Modify the AreTomo command as needed.

AreTomo -InMrc {position_directory}/{position_prefix}_unaligned.mrc -OutMrc {position_directory}/{position_prefix}.mrc -VolZ {aretomo_thickness} -OutBin {aretomo_volume_binning} -TiltCor 1 -AngFile {position_directory}/{position_prefix}.rawtlt -DarkTol {aretomo_DarkTol} -AlignZ {aretomo_AliZ}  -OutImod 3 -FlipVol 1
AreTomo -InMrc {position_directory}/{position_prefix}_unaligned.mrc -OutMrc {position_directory}/{position_prefix}_aligned_stack.mrc -OutBin 4 -VolZ 0 -AlnFile {position_directory}/{position_prefix}.aln


echo "------------------------------------------------------------------------------------"

