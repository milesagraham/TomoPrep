#!/bin/bash
#SBATCH --job-name=mc_stacker
#SBATCH --ntasks={MPIs}
#SBATCH --cpus-per-task={threads}
#SBATCH --output={position_directory}/mc_stacker_{position_prefix}_out.txt
#SBATCH --error={position_directory}/mc_stacker_{position_prefix}_err.txt
#SBATCH --open-mode=append
#SBATCH --partition={partition}
#SBATCH --mem-per-cpu=7G
#SBATCH --exclusive

# Print the exact command into the output file for debugging and to log the
# exact RELION version

module purge
module load {relion_module}

echo "------------------------------------------------------------------------------------"

mkdir {position_directory}/Import
mkdir {position_directory}/Import/job001
cd {position_directory}
relion_import --do_movies --optics_group_name "opticsGroup1" --angpix {pixel_size} --kV {voltage} --Cs {Cs} --Q0 {Q0} --beamtilt_x 0 --beamtilt_y 0 --i "*.{file_type}" --odir Import/job001/ --ofile movies.star --pipeline_control Import/job001/
mpirun -n {MPIs} $(which relion_run_motioncorr_mpi) --i Import/job001/movies.star --o MotionCorr/job002/ --first_frame_sum 1 --last_frame_sum -1 --use_own --j {threads} --bin_factor 1 --bfactor 150 --dose_per_frame {frame_dose} --preexposure 0 --patch_x {motioncorr_patches} --patch_y {motioncorr_patches} --eer_grouping {eer_grouping} --dose_weighting --only_do_unfinished --pipeline_control MotionCorr/job002/ --save_noDW true --gainref {gainref}

module purge
module load {imod_module}
newstack -fileinlist {position_prefix}_newstack.txt -output {position_prefix}_unaligned.mrc
#ccderaser {position_prefix}.st {position_prefix}.st -find

echo "------------------------------------------------------------------------------------"


