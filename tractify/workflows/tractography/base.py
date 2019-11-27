import os
import multiprocessing

import numpy as np
import nibabel as nib
from nipype.pipeline import engine as pe
from nipype.interfaces import fsl, utility as niu
from nipype.utils import NUMPY_MMAP
from nipype.utils.filemanip import fname_presuffix
from numba import cuda
from bids import BIDSLayout

from niworkflows.anat.ants import init_brain_extraction_wf

from ...interfaces import mrtrix3
from ...interfaces import fsl as dmri_fsl
from .outputs import init_tract_output_wf

from nipype.interfaces import fsl, utility as niu

def init_tract_wf():
    tract_wf = pe.Workflow(name="tract_wf")

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "subject_id",
                "session_id",
                "output_dir",
                "t1_file",
                "eddy_file",
                "eddy_mask",
                "eddy_avg_b0"
                "bval",
                "bvec",
                "template",
                "atlas",
                "num_tracts",
            ]
        ),
        name="inputnode",
    )

    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "tck_file",
                "prob_weights",
                "shen_diff_space",
                "inv_len_conmat",
                "len_conmat",
            ]
        ),
        name="outputnode",
    )

    # Skullstrip the t1, needs to map brain on brain
    t1_skullstrip = init_brain_extraction_wf()

    #register T1 to diffusion space first
    #flirt -dof 6 -in T1w_brain.nii.gz -ref nodif_brain.nii.gz -omat xformT1_2_diff.mat -out T1_diff
    flirt = pe.Node(fsl.FLIRT(dof=6), name="t1_flirt")

    to_list = lambda x: [x]

    # T1 should already be skull stripped and minimally preprocessed (from Freesurfer will do)
    #5ttgen fsl -nocrop -premasked T1_diff.nii.gz 5TT.mif
    gen5tt = pe.Node(mrtrix3.Generate5tt(algorithm='fsl', no_crop=True, premasked=True, out_file='5TT.mif'), name="gen5tt")
    #5tt2gmwmi 5TT.mif gmwmi.mif
    gen5ttMask = pe.Node(mrtrix3.Generate5ttMask(out_file='gmwmi.mif'), name="gen5ttMask")

    #SINGLE SHELL
    # generate response function
    #dwi2response tournier data.nii.gz -fslgrad data.eddy_rotated_bvecs dwi.bval response.txt
    responseSD = pe.Node(mrtrix3.ResponseSD(algorithm='tournier'), name="responseSD")
    # generate FODs
    #dwi2fod csd data.nii.gz response.txt FOD.mif -mask nodif_brain_mask.nii.gz -fslgrad data.eddy_rotated_bvecs dwi.bval
    estimateFOD = pe.Node(mrtrix3.EstimateFOD(algorithm='csd', wm_odf='FOD.mif'), name="estimateFOD")
    # perform probabilistic tractography
    #tckgen FOD.mif prob.tck -act 5TT.mif -seed_gmwmi gmwmi.mif -select 5000000 ## seeding from a binarised gmwmi
    tckgen = pe.Node(mrtrix3.Tractography(), name="tckgen")
    #mrview data.nii.gz -tractography.load prob.tck

    def gen_tuple(item1, item2):
        return (item1, item2)

    gen_tuple = pe.Node(
        niu.Function(
            input_names=["item1", "item2"],
            output_names=["out_tuple"],
            function=gen_tuple,
        ),
        name="gen_tuple",
    )
    #use sift to filter tracks based on spherical harmonics
    #tcksift2 prob.tck FOD.mif prob_weights.txt
    tcksift = pe.Node(mrtrix3.TrackSift2(out_weights="prob_weights.txt"), name="tcksift")

    ## atlas reg
    #flirt -in T1w_brain.nii.gz -ref MNI152_T1_1mm_brain.nii.gz -omat xformT1_2_MNI.mat
    pre_atlas_flirt = pe.Node(fsl.FLIRT(), name="pre_atlas_flirt")
    #convert_xfm -omat xformMNI_2_T1.mat -inverse xformT12MNI.mat
    xfm_inv = pe.Node(fsl.ConvertXFM(invert_xfm=True), name="xfm_inv")
    #convert_xfm -omat xformMNI_2_diff.mat -concat xformT1_2_diff.mat xformMNI_2_T1.mat
    xfm_concat = pe.Node(fsl.ConvertXFM(concat_xfm=True), name="xfm_concat")

    #flirt -in shen268.nii.gz -ref T1_diff.nii.gz -applyxfm -init xformMNI_2_diff.mat -interp nearestneighbour -out shen_diff_space.nii.gz
    atlas_flirt = pe.Node(fsl.FLIRT(apply_xfm=True, interp='nearestneighbour'), name="atlas_flirt")

    ## generate connectivity matrices
    #tck2connectome prob.tck shen_diff_space.nii.gz conmat_shen.csv -scale_invlength -zero_diagonal -symmetric -tck_weights_in prob_weights.txt -assignment_radial_search 2 -scale_invnodevol
    conmatgen = pe.Node(mrtrix3.BuildConnectome(out_file="conmat_shen.csv", scale_invlength=True, symmetric=True, zero_diagonal=True, search_radius=2, scale_invnodevol=True), name="conmatgen")
    #tck2connectome prob.tck shen_diff_space.nii.gz conmat_length_shen.csv -zero_diagonal -symmetric -scale_length -stat_edge mean -assignment_radial_search 2
    conmatgen2 = pe.Node(mrtrix3.BuildConnectome(out_file="conmat_length_shen.csv", scale_length=True, symmetric=True, zero_diagonal=True, search_radius=2, stat_edge='mean'), name="conmatgen2")

    # Convert mifs to niftis
    fod_convert = pe.Node(mrtrix3.MRConvert(out_filename="FOD.nii.gz"), name="fod_convert")
    gmwmi_convert = pe.Node(mrtrix3.MRConvert(out_filename="gmwmi.nii.gz"), name="gmwmi_convert")

    # Initialize output wf
    datasink = init_tract_output_wf()

    tract_wf.connect(
        [
            # t1 flirt
            (inputnode, t1_skullstrip, [(("t1_file", to_list), "inputnode.in_files")]),
            (t1_skullstrip, flirt, [("outputnode.out_file", "in_file")]),
            (
                inputnode,
                flirt,
                [
                    ("eddy_avg_b0", "reference")
                ]
            ),
            # response function + mask
            (flirt, gen5tt, [("out_file", "in_file")]),
            (gen5tt, gen5ttMask, [("out_file", "in_file")]),
            (
                inputnode,
                gen_tuple,
                [
                    ("bvec", "item1"),
                    ("bval", "item2")
                ]
            ),
            (gen_tuple, responseSD, [("out_tuple", "grad_fsl")]),
            (inputnode, responseSD, [("eddy_mask", "in_mask")]),
            (
                inputnode,
                responseSD,
                [
                    ("eddy_file", "in_file"),
                ]
            ),
            # FOD gen
            (gen_tuple, estimateFOD, [("out_tuple", "grad_fsl")]),
            (
                inputnode,
                estimateFOD,
                [
                    ("eddy_file", "in_file"),
                ]
            ),
            (responseSD, estimateFOD, [("wm_file", "wm_txt")]),
            (inputnode, estimateFOD, [("eddy_mask", "mask_file")]),
            # tckgen
            (estimateFOD, tckgen, [("wm_odf", "in_file")]),
            (gen5tt, tckgen, [("out_file", "act_file")]),
            (gen5ttMask, tckgen, [("out_file", "seed_gmwmi")]),
            (inputnode, tckgen, [("num_tracts", "select")]),
            # tcksift
            (estimateFOD, tcksift, [("wm_odf", "in_fod")]),
            (tckgen, tcksift, [("out_file", "in_tracks")]),
            # atlas flirt

            (t1_skullstrip, pre_atlas_flirt,[("outputnode.out_file", "in_file")]),
            (inputnode, pre_atlas_flirt,[("template", "reference")]),

            (pre_atlas_flirt, xfm_inv, [("out_matrix_file", "in_file")]),
            (flirt, xfm_concat, [("out_matrix_file", "in_file2")]),
            (xfm_inv, xfm_concat, [("out_file", "in_file")]),
            # Shen atlas register
            (inputnode, atlas_flirt, [("atlas", "in_file")]),
            (flirt, atlas_flirt, [("out_file", "reference")]),
            (xfm_concat, atlas_flirt, [("out_file", "in_matrix_file")]),
            # generate connectivity matrices
            (tckgen, conmatgen, [("out_file", "in_file")]),
            (atlas_flirt, conmatgen, [("out_file", "in_parc")]),
            (tcksift, conmatgen, [("out_weights", "in_weights")]),
            (tckgen, conmatgen2, [("out_file", "in_file")]),
            (atlas_flirt, conmatgen2, [("out_file", "in_parc")]),
            # convert mifs to niftis
            (gen5tt, fod_convert, [("out_file", "in_file")]),
            (gen5ttMask, gmwmi_convert, [("out_file", "in_file")]),
            # outputnode
            (fod_convert, outputnode, [("converted", "fod_file")]),
            (gmwmi_convert, outputnode, [("converted", "gmwmi_file")]),
            (tcksift, outputnode, [("out_weights", "prob_weights")]),
            (atlas_flirt, outputnode, [("out_file", "shen_diff_space")]),
            (conmatgen, outputnode, [("out_file", "inv_len_conmat")]),
            (conmatgen2, outputnode, [("out_file", "len_conmat")]),
            # datasink
            (
                inputnode,
                datasink,
                [
                    ("subject_id", "inputnode.subject_id"),
                    ("session_id", "inputnode.session_id"),
                    ("output_dir", "inputnode.output_folder")
                ]
            ),
            (
                outputnode,
                datasink,
                [
                    ("fod_file", "inputnode.fod_file"),
                    ("gmwmi_file", "inputnode.gmwmi_file"),
                    ("prob_weights", "inputnode.prob_weights"),
                    ("shen_diff_space", "inputnode.shen_diff_space"),
                    ("inv_len_conmat", "inputnode.inv_len_conmat"),
                    ("len_conmat", "inputnode.len_conmat")
                ]
            ),
        ]
    )

    return tract_wf
