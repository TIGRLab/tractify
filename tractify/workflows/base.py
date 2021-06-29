#!/usr/bin/env python

import os
from copy import deepcopy

from nipype.pipeline import engine as pe
from .tractography.base import init_tract_wf
from .tractography.outputs import init_tract_output_wf
from .. import utils

def init_single_ses_wf(subject_id, session_id, parameters):
    t1_file = parameters.t1_file

    if not t1_file:
        raise Exception(
            "No T1 images found for participant {}. "
            "All workflows require T1 images".format(subject_id)
        )

    subject_wf = pe.Workflow(name="single_subject_" + subject_id + "_wf")

    tract_wf = init_tract_wf(parameters.gen5tt_algo)

    tract_wf.base_dir = os.path.join(
        os.path.abspath(parameters.work_dir), "sub-" + subject_id
    )

    inputspec = tract_wf.get_node("inputnode")
    inputspec.inputs.subject_id = subject_id
    inputspec.inputs.session_id = session_id
    inputspec.inputs.output_dir = parameters.output_dir
    inputspec.inputs.t1_file = parameters.t1_file
    inputspec.inputs.fs_file = parameters.fs_file
    inputspec.inputs.eddy_file = parameters.eddy_file
    inputspec.inputs.bvec = parameters.bvec_file
    inputspec.inputs.bval = parameters.bval_file
    inputspec.inputs.template = parameters.template_file
    inputspec.inputs.atlas = parameters.atlas_file
    inputspec.inputs.num_tracts = parameters.num_tracts

    datasink_wf = init_tract_output_wf(
        subject_id=subject_id,
        session_id=session_id
    )

    ds_inputspec = datasink_wf.get_node("inputnode")
    ds_inputspec.inputs.subject_id = subject_id
    ds_inputspec.inputs.session_id = session_id
    ds_inputspec.inputs.output_folder = parameters.output_dir

    wf_name = "sub_" + subject_id + "_ses_" + session_id + "_preproc_wf"
    full_wf = pe.Workflow(name=wf_name)

    full_wf.connect(
        [
            (
                tract_wf,
                datasink_wf,
                [
                    # Outputs
                    ("outputnode.fod_file", "inputnode.fod_file"),
                    ("outputnode.gmwmi_file", "inputnode.gmwmi_file"),
                    ("outputnode.prob_weights", "inputnode.prob_weights"),
                    ("outputnode.shen_diff_space", "inputnode.shen_diff_space"),
                    ("outputnode.inv_len_conmat", "inputnode.inv_len_conmat"),
                    ("outputnode.len_conmat", "inputnode.len_conmat"),
                    ("outputnode.len_invnodevol_conmat", "inputnode.len_invnodevol_conmat"),
                    ("outputnode.sse", "inputnode.sse")
                ],
            )
        ]
    )

    subject_wf.add_nodes([full_wf])
    
    subject_wf.config["execution"]["crashdump_dir"] = os.path.join(
        parameters.output_dir, "tractify_crash", "sub-" + subject_id, "log"
    )

    for node in subject_wf._get_all_nodes():
        node.config = deepcopy(subject_wf.config)

    return subject_wf