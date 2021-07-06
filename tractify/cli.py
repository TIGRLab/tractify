# -*- coding: utf-8 -*-

"""Console script for tractify."""
import os
import sys
import click
from bids import BIDSLayout

from . import utils
from .workflows.base import init_single_ses_wf

class Parameters:
    def __init__(
        self,
        t1_file,
        fs_file,
        eddy_file,
        bval_file,
        bvec_file,
        work_dir,
        output_dir,
        template_file,
        atlas_file,
        gen5tt_algo,
        num_tracts
    ):
        self.t1_file = t1_file
        self.fs_file = fs_file
        self.eddy_file = eddy_file
        self.bval_file = bval_file
        self.bvec_file = bvec_file
        self.work_dir = work_dir
        self.output_dir = output_dir
        self.template_file = template_file
        self.atlas_file = atlas_file
        self.gen5tt_algo = gen5tt_algo
        self.num_tracts = num_tracts

@click.command()
@click.option(
    "--gen5tt-algo",
    help="The algorithm to use for 5ttgen. See "
    "https://mrtrix.readthedocs.io/en/latest/reference/commands/5ttgen.html for details.",
    default='fsl',
)
@click.option(
    "--fs-file",
    help="The aseg file for the subject. Needed if running with --gen5tt-algo=freesurfer."
    "https://mrtrix.readthedocs.io/en/latest/reference/commands/5ttgen.html for details.",
    default=None,
)
@click.option(
    "--num-tracts",
    help="The number of tracts to be generated",
    default=50000,
)
@click.option(
    "--participant-label",
    help="The label(s) of the participant(s) that should be "
    "analyzed. The label corresponds to "
    "sub-<participant_label> from the BIDS spec (so it does "
    "not include 'sub-'). If this parameter is not provided "
    "all subjects will be analyzed. Multiple participants "
    "can be specified with a space separated list.",
    default="001",
)
@click.option(
    "--session-label",
    help="The session id for the given participant."
    "This is for organization purposes and to be"
    "better compliant with bids.",
    default="01",
)
# @click.argument("bids_dir")
# @click.argument("dmriprep_dir")
@click.argument("t1_file")
@click.argument("eddy_file")
@click.argument("bvec_file")
@click.argument("bval_file")
@click.argument("template_file")
@click.argument("atlas_file")
@click.argument("output_dir")

def main(gen5tt_algo, fs_file, num_tracts, participant_label, session_label, t1_file, eddy_file, bvec_file, bval_file, template_file, atlas_file, output_dir):
    """Console script for tractify."""

    work_dir = os.path.join(output_dir, "scratch")

    # Set parameters based on CLI, pass through object
    parameters = Parameters(
        t1_file=t1_file,
        fs_file=fs_file,
        eddy_file=eddy_file,
        bval_file=bval_file,
        bvec_file=bvec_file,
        work_dir=work_dir,
        output_dir=output_dir,
        template_file=template_file,
        atlas_file=atlas_file,
        gen5tt_algo=gen5tt_algo,
        num_tracts=num_tracts
    )

    if (gen5tt_algo == 'freesurfer'):
        try:
            os.environ["SUBJECTS_DIR"]
        except:
            print("No SUBJECTS_DIR environment variable found for"
            " freesurfer, using '" + os.path.dirname(fs_file) + "' instead")
            os.environ["SUBJECTS_DIR"] = os.path.dirname(fs_file)

    wf = init_single_ses_wf(participant_label, session_label, parameters)
    wf.base_dir = parameters.work_dir
    wf.write_graph(graph2use="colored")
    wf.config["execution"]["remove_unnecessary_outputs"] = False
    wf.config["execution"]["keep_inputs"] = True
    wf.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
