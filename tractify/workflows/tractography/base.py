import os
import multiprocessing

import numpy as np
import nibabel as nib
from nipype.pipeline import engine as pe
from nipype.interfaces import fsl, utility as niu
from nipype.utils.filemanip import fname_presuffix
from numba import cuda
from bids import BIDSLayout

from ...interfaces import mrtrix3
from ...interfaces import fsl as dmri_fsl
from .outputs import init_tract_output_wf
from ...utils import gen_tuple
from nipype.interfaces.freesurfer import MRIConvert

from nipype.interfaces import fsl, utility as niu

def init_tract_wf(gen5tt_algo='fsl'):
    tract_wf = pe.Workflow(name="tract_wf")

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "subject_id",
                "session_id",
                "output_dir",
                "t1_file",
                "fs_file",
                "eddy_file",
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
                "5tt_file",
                "prob_weights",
                "atlas_diff_space",
                "len_invnodevol_conmat",
                "gmwmi_file",
                "sse",
            ]
        ),
        name="outputnode",
    )

    # Skullstrip the t1, needs to map brain on brain
    # t1_skullstrip = init_brain_extraction_wf()

    #register T1 to diffusion space first
    #flirt -dof 6 -in T1w_brain.nii.gz -ref nodif_brain.nii.gz -omat xformT1_2_diff.mat -out T1_diff
    flirt = pe.Node(fsl.FLIRT(dof=6), name="t1_flirt")

    to_list = lambda x: [x]
    
    #5tt2gmwmi 5TT.mif gmwmi.mif
    gen5ttMask = pe.Node(mrtrix3.Generate5ttMask(out_file='gmwmi.mif'), name="gen5ttMask")

    #SINGLE SHELL
    # generate response function
    #dwi2response tournier data.nii.gz -fslgrad data.eddy_rotated_bvecs dwi.bval response.txt
    # responseSD = pe.Node(mrtrix3.ResponseSD(algorithm='tournier'), name="responseSD")
    responseSD = pe.Node(mrtrix3.ResponseSD(algorithm='msmt_5tt'), name="responseSD")
    # generate FODs
    #dwi2fod msmt_csd data.nii.gz response.txt FOD.mif -mask nodif_brain_mask.nii.gz -fslgrad data.eddy_rotated_bvecs dwi.bval
    estimateFOD = pe.Node(mrtrix3.EstimateFOD(algorithm='msmt_csd', wm_odf='FOD.mif'), name="estimateFOD")
    # perform probabilistic tractography
    #tckgen FOD.mif prob.tck -act 5TT.mif -seed_gmwmi gmwmi.mif -select 5000000 ## seeding from a binarised gmwmi
    tckgen = pe.Node(mrtrix3.Tractography(), name="tckgen")
    #mrview data.nii.gz -tractography.load prob.tck

    gen_grad_tuple = pe.Node(
        niu.Function(
            input_names=["item1", "item2"],
            output_names=["out_tuple"],
            function=gen_tuple,
        ),
        name="gen_grad_tuple",
    )
    #use sift to filter tracks based on spherical harmonics
    #tcksift2 prob.tck FOD.mif prob_weights.txt
    tcksift = pe.Node(mrtrix3.TrackSift2(out_weights="prob_weights.txt"), name="tcksift")

    ## atlas reg
    #flirt -in T1w_brain.nii.gz -ref MNI152_T1_1mm_brain.nii.gz -omat xformT1_2_MNI.mat
    pre_atlas_flirt = pe.Node(fsl.FLIRT(), name="pre_atlas_flirt")
    #convert_xfm -omat xformMNI_2_T1.mat -inverse xformT12MNI.mat (inverse, now MNI -> T1)
    xfm_inv = pe.Node(fsl.ConvertXFM(invert_xfm=True), name="xfm_inv")
    #convert_xfm -omat xformMNI_2_diff.mat -concat xformT1_2_diff.mat xformMNI_2_T1.mat (concatenating MNI -> T1 + T1 -> diff, now MNI -> diff)
    xfm_concat = pe.Node(fsl.ConvertXFM(concat_xfm=True), name="xfm_concat")

    #flirt -in shen268.nii.gz -ref T1_diff.nii.gz -applyxfm -init xformMNI_2_diff.mat -interp nearestneighbour -out shen_diff_space.nii.gz (shen to diffusion space, using MNI->diff)
    atlas_flirt = pe.Node(fsl.FLIRT(apply_xfm=True, interp='nearestneighbour'), name="atlas_flirt")

    ## generate connectivity matrices
    conmatgen3 = pe.Node(mrtrix3.BuildConnectome(out_file="conmat_length_invnodevol.csv", scale_invnodevol=True, scale_length=True, symmetric=True, zero_diagonal=True, search_radius=4, keep_unassigned=True), name="conmatgen3")

    # Convert mifs to niftis
    gen5tt_convert = pe.Node(mrtrix3.MRConvert(out_filename="5TT.nii.gz"), name="gen5tt_convert")
    gmwmi_convert = pe.Node(mrtrix3.MRConvert(out_filename="gmwmi.nii.gz"), name="gmwmi_convert")

    # Bias the eddy using mrtrix3
    eddy_biascorrect = pe.Node(mrtrix3.DWIBiasCorrect(out_file="data_ud_biascorrect_ants.nii.gz", use_ants=True), name="eddy_biascorrect_ants")

    # Extract b0s from the eddy using mrtrix3
    eddy_extract_b0 = pe.Node(mrtrix3.DWIExtract(bzero=True, out_file="data_ud_b0.nii.gz", export_grad_fsl=("data_ud_b0.new_bvecs", "data_ud_b0.new_bval")), name="eddy_extract_b0")

    # Avg out the b0s from eddy
    eddy_mean_b0 = pe.Node(mrtrix3.MRMath(operation='mean', axis=3), name="eddy_mean_b0")

    # dilate mask (eddy)
    eddy_b0_mask = pe.Node(
        fsl.BET(frac=0.5, mask=True, robust=True),
        name="eddy_b0_mask",
    )

    # Extract b1000 from the eddy using mrtrix3
    eddy_extract_b1000 = pe.Node(mrtrix3.DWIExtract(shell=[0,1000], out_file="data_ud_b1000.nii.gz", export_grad_fsl=("data_ud_b1000.new_bvecs", "data_ud_b1000.new_bval")), name="eddy_extract_b1000")

    # Mask extracted b1000
    eddy_b1000_mask = pe.Node(
        fsl.BET(frac=0.5, mask=True, robust=True),
        name="eddy_b1000_mask",
    )

    # Initialize output wf
    # datasink = init_tract_output_wf()

    # T1 should already be skull stripped and minimally preprocessed (from Freesurfer will do)
    #5ttgen fsl -nocrop -premasked T1_diff.nii.gz 5TT.mif
    if (gen5tt_algo == 'fsl'):
        gen5tt = pe.Node(mrtrix3.Generate5tt(algorithm='fsl', no_crop=True, premasked=True, out_file='5TT.mif'), name="gen5tt")
        tract_wf.connect(
            [
                # t1 flirt (taking this out because t1s are assumed already skullstripped in this version)
                (flirt, gen5tt, [("out_file", "in_file")]),
            ]
        )
    elif (gen5tt_algo == 'freesurfer'):
        # Convert the aseg.mgz from freesurfer to nii.gz 
        # fs_convert_mgz = pe.Node(MRIConvert(in_type='mgz', out_type='niigz', out_file='aseg.nii.gz'), name="fs_convert_mgz")
        gen5tt = pe.Node(mrtrix3.Generate5tt(algorithm='freesurfer', no_crop=True, out_file='5TT.mif'), name="gen5tt")
        tract_wf.connect(
            [
                # Pass in freesurfer aseg to gen5tt
                (inputnode, gen5tt, [("fs_file", "in_file")])
            ]
        )
    else:
        raise Exception(
            "Invalid algorithm for 5ttgen {}. "
            "Valid algorithms are freesurfer and fsl".format(subject_id)
        )

    # Output the sse from dtifit
    dtifit = pe.Node(dmri_fsl.DTIFit(save_tensor=True, sse=True), name="dtifit")

    tract_wf.connect(
        [
            # t1 flirt (taking this out because t1s are assumed already skullstripped in this version)
            (inputnode, flirt, [("t1_file", "in_file")]),
            # response function + mask
            (gen5tt, gen5ttMask, [("out_file", "in_file")]),
            # Combining the bval and bvec from eddy
            (
                inputnode,
                gen_grad_tuple,
                [
                    ("bvec", "item1"),
                    ("bval", "item2")
                ]
            ),
            (gen_grad_tuple, responseSD, [("out_tuple", "grad_fsl")]),
            # Bias correct eddy
            (inputnode, eddy_biascorrect, [("eddy_file", "in_file")]),
            (gen_grad_tuple, eddy_biascorrect, [("out_tuple", "grad_fsl")]),
            # Averaging out b0 from mrmath
            (eddy_biascorrect, eddy_extract_b0, [("out_file", "in_file")]),
            # Extracting b0 from eddy
            # (inputnode, eddy_extract_b0, [("eddy_file", "in_file")]),
            (gen_grad_tuple, eddy_extract_b0, [("out_tuple", "grad_fsl")]),
            # Averaging out b0 from mrmath
            (eddy_extract_b0, eddy_mean_b0, [("out_file", "in_file")]),
            (eddy_b0_mask, flirt, [("out_file", "reference")]),
            # Skulstrip b0 using BET
            (eddy_mean_b0, eddy_b0_mask, [("out_file", "in_file")]),
            # Generate eddy mask and then feed into responseSD
            (eddy_b0_mask, responseSD, [("mask_file", "in_mask")]),
            (inputnode, responseSD, [("eddy_file", "in_file")]),
            (gen5tt, responseSD, [("out_file", "mtt_file")]),
            # FOD generation
            (gen_grad_tuple, estimateFOD, [("out_tuple", "grad_fsl")]),
            (inputnode, estimateFOD, [("eddy_file", "in_file")]),
            (responseSD, estimateFOD, [("wm_file", "wm_txt")]),
            (responseSD, estimateFOD, [("gm_file", "gm_txt")]),
            (responseSD, estimateFOD, [("csf_file", "csf_txt")]),
            (eddy_b0_mask, estimateFOD, [("mask_file", "mask_file")]),
            # tckgen
            (estimateFOD, tckgen, [("wm_odf", "in_file")]),
            (gen5tt, tckgen, [("out_file", "act_file")]),
            (gen5ttMask, tckgen, [("out_file", "seed_gmwmi")]),
            (inputnode, tckgen, [("num_tracts", "select")]),
            # tcksift
            (estimateFOD, tcksift, [("wm_odf", "in_fod")]),
            (tckgen, tcksift, [("out_file", "in_tracks")]),
            # atlas flirt
            (inputnode, pre_atlas_flirt,[("t1_file", "in_file")]),
            (inputnode, pre_atlas_flirt,[("template", "reference")]),
            (pre_atlas_flirt, xfm_inv, [("out_matrix_file", "in_file")]),
            (flirt, xfm_concat, [("out_matrix_file", "in_file2")]),
            (xfm_inv, xfm_concat, [("out_file", "in_file")]),
            # Atlas register
            (inputnode, atlas_flirt, [("atlas", "in_file")]),
            (flirt, atlas_flirt, [("out_file", "reference")]),
            (xfm_concat, atlas_flirt, [("out_file", "in_matrix_file")]),
            # Generate connectivity matrices
            (tckgen, conmatgen3, [("out_file", "in_file")]),
            (atlas_flirt, conmatgen3, [("out_file", "in_parc")]),
            (tcksift, conmatgen3, [("out_weights", "in_weights")]),
            # convert mifs to niftis
            (gen5tt, gen5tt_convert, [("out_file", "in_file")]),
            (gen5ttMask, gmwmi_convert, [("out_file", "in_file")]),
            # Extracting b1000 from eddy
            (eddy_biascorrect, eddy_extract_b1000, [("out_file", "in_file")]),
            (gen_grad_tuple, eddy_extract_b1000, [("out_tuple", "grad_fsl")]),
            # Skulstrip b1000 using BET
            (eddy_extract_b1000, eddy_b1000_mask, [("out_file", "in_file")]),
            # Generate sse from dtifit
            (eddy_extract_b1000, dtifit, [("out_file", "dwi")]),
            (eddy_b1000_mask, dtifit, [("mask_file", "mask")]),
            (eddy_extract_b1000, dtifit, [("export_bval", "bvals")]),
            (eddy_extract_b1000, dtifit, [("export_bvec", "bvecs")]),
            # Outputnode
            (gen5tt_convert, outputnode, [("converted", "5tt_file")]),
            (gmwmi_convert, outputnode, [("converted", "gmwmi_file")]),
            (tcksift, outputnode, [("out_weights", "prob_weights")]),
            (atlas_flirt, outputnode, [("out_file", "atlas_diff_space")]),
            (conmatgen3, outputnode, [("out_file", "len_invnodevol_conmat")]),
            (dtifit, outputnode, [("sse", "sse")]),
        ]
    )

    return tract_wf
