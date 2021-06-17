# Tractify Pipeline

![tract](https://user-images.githubusercontent.com/54225067/122474320-0d94df80-cf91-11eb-86c9-066c1adffb39.png)

### About

Tractify is an efficient and reproducible tractography pipeline built with [Nipype](https://nipype.readthedocs.io/en/latest/). This allows anyone to get started with tractography generation by packaging a pipeline based on [MRtrix3's tractography tools](https://mrtrix.readthedocs.io/en/latest/reference/commands_list.html) and containerising it to run on any platform.

As previously mentioned, this pipeline is based on MRtrix3's tractography tools to generate tracts using a probabilistic approach. The pipeline has many nodes to ensure everything runs smoothly, but the core of the pipeline can be summarized as such:
1. Extract grey/white matter interface from T1 (using [5ttgen](https://mrtrix.readthedocs.io/en/latest/reference/commands/5ttgen.html))
2. Generate response function from DWI (using [dwi2response](https://mrtrix.readthedocs.io/en/latest/reference/commands/dwi2response.html))
3. Estimate fibre orientation distributions from DWI and response function(using [dwi2fod](https://mrtrix.readthedocs.io/en/latest/reference/commands/dwi2fod.html))
4. Generate tracts from FOD and grey/white matter interface (using [tckgen](https://mrtrix.readthedocs.io/en/latest/reference/commands/tckgen.html))

A visual for this process is shown below: 

![method](https://user-images.githubusercontent.com/54225067/122474400-29988100-cf91-11eb-8da2-59fb303b7b3a.png)

After the tracts are generated and filtered (using [tcksift2](https://mrtrix.readthedocs.io/en/latest/reference/commands/tcksift2.html)) the pipeline generates connectivity matrices for analysis. Two connectivity matrices are made using [tck2connectome](https://mrtrix.readthedocs.io/en/latest/reference/commands/tck2connectome.html), one scaling connectome edge contributions by length, and one scaling by inverse length ([see here in the docs for more info](https://mrtrix.readthedocs.io/en/latest/reference/commands/tck2connectome.html#structural-connectome-metric-options)).

### Running the Pipeline

**Setup**

You must have preprocessed diffusion data before running this pipeline. Specifically, the pipeline will be looking for head motion-corrected `nii.gz` diffusion files for each subject. This version of the pipeline does not require the data to be in bids, so you can just pass in the file path for each individual subject. 

**If you are running locally**: you must set up your python environment and ensure you have the required modules loaded. Setting up your python environment is as simple as running the following in the directory where you pulled this repository: 
```
pip install .
```
After running the above, you should have tractify available as a command.

As for the modules, tractify requires *at least* the listed versions of the following packages:
```
FSL/6.0.1
MRtrix3/3
```
This is to use FSL's registration tools and MRtrix3's tractography tools.

**If you are running using a container**: you don't have to worry about the above. Just run the container while binding the files and folders when you run tractify. More info at the  **Containers** section.

**Usage**

You can run tractify for a subject as follows:

```
tractify <t1> <dwi> <bval> <bvec> <template> <atlas> <output_dir> \
  --participant-label <sub_id> \
  --session-label <session_id>
```

As you can see, there are other data you need to pass in aside from the diffusion data for each subject. They can be described as follows: 

- `t1`: The skullstripped anatomical T1 data.
- `dwi`: The preprocessed diffusion data.
- `bval`: The bval file for the preprocessed diffusion data.
- `bvec`: The bvec file for the preprocessed diffusion data.
- `template`: The template file for T1 registration (ex. [the MNI 152 non-linear template](http://nist.mni.mcgill.ca/mni-icbm152-non-linear-6th-generation-symmetric-average-brain-stereotaxic-registration-model/)).
- `atlas`: The atlas file for parcellating the data for tractography (ex. [the Shen k=268 atlas](https://neurovault.org/images/395091/)).
- `output_dir`: The base location of where all subject tractify outputs will be placed.
- `--participant-label`: The id of the subject's data being run through the pipeline, for output organization (optional, default `None`).
- `--session-label`: The id of the subject's session data being run through the pipeline, for output organization (optional, default `sub-001`).
- `--num-tracts`: The id of the subject's session data being run through the pipeline, for output organization (optional, default 5000000).

**Outputs**

Once you run the pipeline, you will get an output that looks like the following:
```
output_dir
└── tractify
    └── sub-{id}
        └── ses-01
            ├── sub-{id}_ses-01_desc-conmat-length.csv
            ├── sub-{id}_ses-01_desc-conmat-invlength.csv
            ├── sub-{id}_ses-01_desc-fod.nii.gz
            ├── sub-{id}_ses-01_desc-gwmatter.nii.gz
            ├── sub-{id}_ses-01_desc-prob-weights.txt
            └── sub-{id}_ses-01_desc-atlas-register.nii.gz
```
These outputs can be described as follows:
- `conmat-length.csv`: The connectivity matrix scaling connectome edge contributions by length.
- `conmat-invlength.csv`: The connectivity matrix scaling connectome edge contributions by inverse length.
- `fod.nii.gz`: The FOD generated from the dwi and response function.
- `gwmatter.nii.gz`: The gray white matter interface generated from the T1.
- `prob-weights.txt`: The probability weights interface generated from the tracts (see [tcksift2](https://mrtrix.readthedocs.io/en/latest/reference/commands/tcksift2.html)).
- `atlas-register.nii.gz`: The chosen atlas registered to diffusion space.

In addition to the standard outputs, all of the intermediate outputs will be saved in output_dir/scratch, organized by nodes from the Nipype framework. These are here in case you want to dig for a specific intermediate output, as well as for rerunning the pipeline (Nipype will recognize what has already been run and start from the previous run). For example, the tract file (which can quickly add up in size for large datasets) would be saved at `output_dir/scratch/single_subject-{id}_wf/sub-{id}_ses_01_preproc_wf/tract_wf/tckgen/tracked.tck`. 

*If you don't want to keep these files, delete the `output_dir/scratch` folder after running tractify!*

**Containers**

If you are using [Singularity](https://sylabs.io/singularity/) containers to run this data, there are not a real list of dependencies that you need to worry about. You just need a way to run Singularity (version 2.xx) on your platform. 

All you need now is the singularity image `tractify.simg` and then you can run the following:
```
singularity run \
  -H <sing_home> \
  -B <t1>:/t1.nii.gz \
  -B <dwi>:/dwi.nii.gz \
  -B <bval>:/dwi.bval \
  -B <bvec>:/dwi.bvec \
  -B <template>:/template.nii.gz \
  -B <atlas>:/atlas.nii.gz \
  -B <output_dir>:/out \
  tractify.simg /t1.nii.gz /dwi.nii.gz /dwi.bval /dwi.bvec 
    /template.nii.gz /atlas.nii.gz /out \
    --participant-label <sub_id> \
    --session-label <session_id>
```
Note: `<sing_home>` is just a folder singularity needs to point to for its temporary data. It's suggested to just create an empty directory to point to before running.

You can build the containers and singularity image from scratch using [Docker](https://docs.docker.com/get-started/) on the appropriate Dockerfile and using [docker2singularity](https://github.com/singularityhub/docker2singularity) to convert it into a Singularity image. For example, you can rebuild the tractify container by running the following in this repo's directory:

```
# Build the container using Docker
docker build . -t tractify:latest
# Convert the container to a Singularity image
docker run --privileged -t --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ${output_directory}:/output \
  singularityware/docker2singularity \
  tractify:latest
```
