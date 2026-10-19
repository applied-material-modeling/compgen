# Instructions for compiling Racoon/Moose on Aurora. 

Note that there seems to be some non-optimal environment stuff going on in the original (and these) instructions. A copy of Moose is taken from Conda, which contains things like libmesh. We install this into some Python environment (/home/bbrunsvik/environments/moose in this case). Then, we clone racoon, and we get another copy of Moose in that folder (/home/bbrunsvik/projects/raccoon/moose). We need to have the Conda version of Moose in our path so that libmesh and other things are available when we compile racoon. So, both folders of Moose are being used at the same time while compiling racoon. Confusing! 

## 1. Load the miniforge3 module
module load miniforge3

## 2. Navigate to your projects directory and place my environment.yml file there. 
cd /home/bbrunsvik/projects

Note that using my environment file is equivalent to the conda installation instructions from https://hugary1995.github.io/raccoon/getting_started/install or https://mooseframework.inl.gov/getting_started/installation/conda.html

## 3. Create the conda environment. Use -p to decide where your Python environment will go. 

Note that I placed the environment file here: /home/bbrunsvik/Documents/ains/code/compgen/raccoon_brb/environment.yml

conda env create -f environment.yml -p /home/bbrunsvik/environments/moose

conda activate /home/bbrunsvik/environments/moose

## 4. Navigate to where you want the raccoon project directory
cd /home/bbrunsvik/projects

## 5. Clone the RACCOON repository
git clone https://github.com/hugary1995/raccoon.git

## 6. Enter the cloned directory
cd raccoon
git checkout master

## 7. Download RACCOON and MOOSE submodules
## These commands download a copy of RACCOON and MOOSE (as a submodule) to your local projects directory, aparently among other things. 
git submodule update --init --recursive

## 8. Add the conda environment to your PATH
export PATH="/home/bbrunsvik/environments/moose/bin:$PATH"

## 9. Verify Python points to the conda environment (MUST point to miniconda3/envs/...)
which python3

## 10. Build racoon. 
make -j 4

## 11. Make sure it all runs. 
./run_tests -j N

# Additional installation information
Standard installation instructions are here: https://hugary1995.github.io/raccoon/getting_started/install.html but they did not work for me. libmesh and other packages were not available when trying to compile racoon. Using the installation instructions on this website to compile libmesh led to an extraordinarily long compilation time. 

# Ryley's installation instructions worked much better for me. I modified my instructions above from his information. If you have problem with my instructions above, maybe these alternative instructions will be helpful. 

conda init --all
exit

(base) ->  # Make sure you have conda should see (base) at command line..
conda update --all --yes
conda config --add channels https://conda.software.inl.gov/public
conda config --add channels conda-forge

conda create -n racoon moose-dev=2026.02.20=mpich

conda activate racoon

(racoon) ->
cd [path where you want to install racoon]
git clone https://github.com/hugary1995/raccoon.git
cd raccoon
git submodule update --init --recursive # These commands should download a copy of RACCOON and a copy of MOOSE (as a submodule) to your local projects directory.

#conda install -c conda-forge bison flex
#./moose/scripts/update_and_rebuild_petsc.sh --download-bison=1 #~ maybe not needed??


conda install -c conda-forge python=3.10 
#something strange about my python3 on mac

1. Force your terminal to look in the racoon conda env first for EVERYTHING
export PATH="/Users/rghill/miniconda3/envs/racoon/bin:$PATH"

2. Verify that `python3` now points to conda (it MUST point to miniconda3/envs/...)
which python3

3. IF step 2 worked, run the basic make command without any extra variables
make -j 4



