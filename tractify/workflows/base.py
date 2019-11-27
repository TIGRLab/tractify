#!/usr/bin/env python

import os
from copy import deepcopy

from nipype.pipeline import engine as pe
from .tractography.base import init_tract_wf
from .. import utils

def init_tractify_wf(parameters):
    tractify_wf = pe.Workflow(name="tractify_wf")
    tractify_wf.base_dir = parameters.work_dir

    for subject_id in parameters.subject_list:

        single_subject_wf = init_single_subject_wf(
            subject_id=subject_id,
            name="single_subject_" + subject_id + "_wf",
            parameters=parameters,
        )

        single_subject_wf.config["execution"]["crashdump_dir"] = os.path.join(
            parameters.output_dir, "tractify_crash", "sub-" + subject_id, "log"
        )

        for node in single_subject_wf._get_all_nodes():
            node.config = deepcopy(single_subject_wf.config)

        tractify_wf.add_nodes([single_subject_wf])

    return tractify_wf

def init_single_subject_wf(subject_id, name, parameters):
    t1_files = parameters.layout.get(
        subject=subject_id,
        suffix="T1w",
        extensions=[".nii", ".nii.gz"],
        return_type="filename"
    )

    if not t1_files:
        raise Exception(
            "No T1 images found for participant {}. "
            "All workflows require T1 images".format(subject_id)
        )

    subject_wf = pe.Workflow(name=name)

    for t1_file in t1_files:
        try:
            entities = parameters.layout.parse_file_entities(t1_file)
            if "session" in entities:
                session_id = entities["session"]
            else:
                session_id = "01"
            metadata = parameters.layout.get_metadata(t1_file)
            tract_wf = init_tract_wf()

            tract_wf.base_dir = os.path.join(
                os.path.abspath(parameters.work_dir), subject_id
            )

            dmripreproc_output = utils.collect_dmripreproc_output(
                dmriprep_dir=parameters.dmriprep_dir,
                subject_id=subject_id,
                session_id=session_id
            )

            inputspec = tract_wf.get_node("inputnode")
            inputspec.inputs.subject_id = subject_id
            inputspec.inputs.session_id = session_id
            inputspec.inputs.output_dir = parameters.output_dir
            inputspec.inputs.t1_file = t1_file
            inputspec.inputs.eddy_file = dmripreproc_output['eddy_file']
            inputspec.inputs.eddy_avg_b0 = dmripreproc_output['eddy_avg_b0']
            inputspec.inputs.eddy_mask = dmripreproc_output['eddy_mask']
            inputspec.inputs.bvec = dmripreproc_output['bvec']
            inputspec.inputs.bval = dmripreproc_output['bval']
            inputspec.inputs.template = parameters.template_file
            inputspec.inputs.atlas = parameters.atlas_file
            inputspec.inputs.num_tracts = parameters.num_tracts

            wf_name = "sub_" + subject_id + "_ses_" + session_id + "_preproc_wf"
            full_wf = pe.Workflow(name=wf_name)

            full_wf.add_nodes([tract_wf])

            subject_wf.add_nodes([full_wf])
        except:
            print("Dmriprep files not found for participant {} session {}.".format(subject_id, session_id))

    return subject_wf
