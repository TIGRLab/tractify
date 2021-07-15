#!/usr/bin/env python

import os

from nipype.pipeline import engine as pe
from nipype.interfaces import io as nio, utility as niu

def init_tract_output_wf(subject_id, session_id):

    op_wf = pe.Workflow(name="output_wf")

    # Outputs are tckgen, atlas_diff_space, conmat1, conmat2, prob_weights

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "subject_id",
                "session_id",
                "output_folder",
                "prob_weights",
                "5tt_file",
                "gmwmi_file",
                "atlas_diff_space",
                "len_invnodevol_conmat",
                "sse"
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
    conmat_length_invnodevol_rename = pe.Node(niu.Rename(format_string=template.format("conmat-length-invnodevol") + ".csv"), name="conmat_length_invnodevol_rename")
    sse_rename = pe.Node(niu.Rename(format_string=template.format("sse"), keep_ext=True), name="sse_rename")
    gen5tt_rename = pe.Node(niu.Rename(format_string=template.format("5tt"), keep_ext=True), name="gen5tt_rename")
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
            (inputnode, conmat_length_invnodevol_rename, [("len_invnodevol_conmat", "in_file")]),
            (inputnode, sse_rename, [("sse", "in_file")]),
            (inputnode, gen5tt_rename, [("5tt_file", "in_file")]),
            (inputnode, probweights_rename, [("prob_weights", "in_file")]),
            (inputnode, shenreg_rename, [("atlas_diff_space", "in_file")]),
            (inputnode, gwmatter_rename, [("gmwmi_file", "in_file")]),
            # Outputting the renamed files
            (conmat_length_invnodevol_rename, datasink, [("out_file", "@result.@len_invnodevol_conmat")]),
            (sse_rename, datasink, [("out_file", "@result.@sse")]),
            (gen5tt_rename, datasink, [("out_file", "@result.@5tt_file")]),
            (probweights_rename, datasink, [("out_file", "@result.@prob_weights")]),
            (shenreg_rename, datasink, [("out_file", "@result.@atlas_diff_space")]),
            (gwmatter_rename, datasink, [("out_file", "@result.@gmwmi_file")])
        ]
    )

    return op_wf
