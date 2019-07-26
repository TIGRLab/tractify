#!/usr/bin/env python

import os

from nipype.pipeline import engine as pe
from nipype.interfaces import io as nio, utility as niu

def init_tract_output_wf():

    op_wf = pe.Workflow(name="output_wf")

    # Outputs are tckgen, shen_diff_space, conmat1, conmat2, prob_weights

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "subject_id",
                "session_id",
                "output_folder",
                "prob_weights",
                "fod_file",
                "gmwmi_file",
                "shen_diff_space",
                "inv_len_conmat",
                "len_conmat"
            ]
        ),
        name="inputnode",
    )

    def build_path(output_folder, subject_id, session_id):
        import os

        return os.path.join(
            output_folder,
            "tractify",
            "sub-" + subject_id,
            "ses-" + session_id,
            "dwi",
        )

    concat = pe.Node(
        niu.Function(
            input_names=["output_folder", "subject_id", "session_id"],
            output_names=["built_folder"],
            function=build_path,
        ),
        name="build_path",
    )

    datasink = pe.Node(nio.DataSink(), name="datasink")

    op_wf.connect(
        [
            (
                inputnode,
                concat,
                [
                    ("subject_id", "subject_id"),
                    ("session_id", "session_id"),
                    ("output_folder", "output_folder"),
                ],
            ),
            (concat, datasink, [("built_folder", "base_directory")]),
            (
                inputnode,
                datasink,
                [
                    ("prob_weights", "@result.@prob_weights"),
                    ("shen_diff_space", "@result.@shen_diff_space"),
                    ("inv_len_conmat", "@result.@inv_len_conmat"),
                    ("fod_file", "@result.@fod_file"),
                    ("gmwmi_file", "@result.@gmwmi_file"),
                    ("len_conmat", "@result.@len_conmat")
                ],
            ),
        ]
    )

    return op_wf
