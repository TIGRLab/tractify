#!/usr/bin/env python

import os

from nipype.pipeline import engine as pe
from nipype.interfaces import io as nio, utility as niu

def init_tract_output_wf(subject_id, session_id):

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
                "len_invnodevol_conmat",
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

    # Rename Nodes
    prefix = "sub-{}_ses-{}".format(subject_id, session_id)
    template = prefix + "_desc-{}"
    conmat_length_rename = pe.Node(niu.Rename(format_string=template.format("conmat-length") + ".csv"), name="conmat_length_rename")
    conmat_length_invnodevol_rename = pe.Node(niu.Rename(format_string=template.format("conmat-length-invnodevol") + ".csv"), name="conmat_length_invnodevol_rename")
    conmat_invlength_rename = pe.Node(niu.Rename(format_string=template.format("conmat-invlength") + ".csv"), name="conmat_invlength_rename")
    fod_rename = pe.Node(niu.Rename(format_string=template.format("fod"), keep_ext=True), name="fod_rename")
    gwmatter_rename = pe.Node(niu.Rename(format_string=template.format("gwmatter"), keep_ext=True), name="gwmatter_rename")
    probweights_rename = pe.Node(niu.Rename(format_string=template.format("prob-weights"), keep_ext=True), name="probweights_rename")
    shenreg_rename = pe.Node(niu.Rename(format_string=template.format("atlas-register"), keep_ext=True), name="shenreg_rename")

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
            # Renaming the files
            (inputnode, conmat_length_rename, [("len_conmat", "in_file")]),
            (inputnode, conmat_length_invnodevol_rename, [("len_invnodevol_conmat", "in_file")]),
            (inputnode, conmat_invlength_rename, [("inv_len_conmat", "in_file")]),
            (inputnode, fod_rename, [("fod_file", "in_file")]),
            (inputnode, probweights_rename, [("prob_weights", "in_file")]),
            (inputnode, shenreg_rename, [("shen_diff_space", "in_file")]),
            (inputnode, gwmatter_rename, [("gmwmi_file", "in_file")]),
            # Outputting the renamed files
            (conmat_length_rename, datasink, [("out_file", "@result.@len_conmat")]),
            (conmat_length_invnodevol_rename, datasink, [("out_file", "@result.@len_invnodevol_conmat")]),
            (conmat_invlength_rename, datasink, [("out_file", "@result.@inv_len_conmat")]),
            (fod_rename, datasink, [("out_file", "@result.@fod_file")]),
            (probweights_rename, datasink, [("out_file", "@result.@prob_weights")]),
            (shenreg_rename, datasink, [("out_file", "@result.@shen_diff_space")]),
            (gwmatter_rename, datasink, [("out_file", "@result.@gmwmi_file")])
        ]
    )

    return op_wf
