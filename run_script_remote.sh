#!/bin/bash
#SBATCH --job-name=preprocess
#SBATCH --ntasks=15
#SBATCH --output=preprocess_out.txt
#SBATCH --error=preprocess_err.txt
#SBATCH --open-mode=append
#SBATCH --partition=relion
#SBATCH --mem-per-cpu=7G



module load ANACONDA/3
python MG_preprocess_job_limit.py

