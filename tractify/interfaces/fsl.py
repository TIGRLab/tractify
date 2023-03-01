#!/usr/bin/env python

from __future__ import (
    print_function,
    division,
    unicode_literals,
    absolute_import,
)

from builtins import str

import os
import os.path as op

import numpy as np
import nibabel as nb
import warnings

from nipype.interfaces.base import traits, TraitedSpec, InputMultiPath, File, isdefined
from nipype.interfaces.fsl.base import FSLCommand, FSLCommandInputSpec, Info
from nipype.interfaces.freesurfer.base import FSCommand, FSTraitedSpec

class ConvertXFMInputSpec(FSLCommandInputSpec):
    in_file = File(exists=True, mandatory=True, argstr="%s", position=-1,
                   desc="input transformation matrix")
    in_file2 = File(exists=True, argstr="%s", position=-2,
                    desc=("second input matrix (for use with fix_scale_skew or "
                          "concat_xfm"))
    _options = ["invert_xfm", "concat_xfm", "fix_scale_skew"]
    invert_xfm = traits.Bool(argstr="-inverse", position=-3, xor=_options,
                             desc="invert input transformation")
    concat_xfm = traits.Bool(argstr="-concat", position=-3, xor=_options,
                             requires=["in_file2"],
                             desc=("write joint transformation of two input "
                                   "matrices"))
    fix_scale_skew = traits.Bool(argstr="-fixscaleskew", position=-3,
                                 xor=_options, requires=["in_file2"],
                                 desc=("use secondary matrix to fix scale and "
                                       "skew"))
    out_file = File(genfile=True, argstr="-omat %s", position=1,
                    desc="final transformation matrix", hash_files=False)


class ConvertXFMOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc="output transformation matrix")


class ConvertXFM(FSLCommand):
    """Use the FSL utility convert_xfm to modify FLIRT transformation matrices.
    Examples
    --------
    >>> import nipype.interfaces.fsl as fsl
    >>> invt = fsl.ConvertXFM()
    >>> invt.inputs.in_file = "flirt.mat"
    >>> invt.inputs.invert_xfm = True
    >>> invt.inputs.out_file = 'flirt_inv.mat'
    >>> invt.cmdline
    'convert_xfm -omat flirt_inv.mat -inverse flirt.mat'
    """

    _cmd = "convert_xfm"
    input_spec = ConvertXFMInputSpec
    output_spec = ConvertXFMOutputSpec

    def _list_outputs(self):
        outputs = self._outputs().get()
        outfile = self.inputs.out_file
        if not isdefined(outfile):
            _, infile1, _ = split_filename(self.inputs.in_file)
            if self.inputs.invert_xfm:
                outfile = fname_presuffix(infile1,
                                          suffix="_inv.mat",
                                          newpath=os.getcwd(),
                                          use_ext=False)
            else:
                if self.inputs.concat_xfm:
                    _, infile2, _ = split_filename(self.inputs.in_file2)
                    outfile = fname_presuffix("%s_%s" % (infile1, infile2),
                                              suffix=".mat",
                                              newpath=os.getcwd(),
                                              use_ext=False)
                else:
                    outfile = fname_presuffix(infile1,
                                              suffix="_fix.mat",
                                              newpath=os.getcwd(),
                                              use_ext=False)
        outputs["out_file"] = os.path.abspath(outfile)
        return outputs

    def _gen_filename(self, name):
        if name == "out_file":
            return self._list_outputs()["out_file"]
        return None

class DTIFitInputSpec(FSLCommandInputSpec):
    dwi = File(exists=True, desc='diffusion weighted image data file',
               argstr='-k %s', position=0, mandatory=True)
    base_name = traits.Str("dtifit_", desc='base_name that all output files will start with',
                           argstr='-o %s', position=1, usedefault=True)
    mask = File(exists=True, desc='bet binary mask file',
                argstr='-m %s', position=2, mandatory=True)
    bvecs = File(exists=True, desc='b vectors file',
                 argstr='-r %s', position=3, mandatory=True)
    bvals = File(exists=True, desc='b values file',
                 argstr='-b %s', position=4, mandatory=True)
    min_z = traits.Int(argstr='-z %d', desc='min z')
    max_z = traits.Int(argstr='-Z %d', desc='max z')
    min_y = traits.Int(argstr='-y %d', desc='min y')
    max_y = traits.Int(argstr='-Y %d', desc='max y')
    min_x = traits.Int(argstr='-x %d', desc='min x')
    max_x = traits.Int(argstr='-X %d', desc='max x')
    save_tensor = traits.Bool(desc='save the elements of the tensor',
                              argstr='--save_tensor')
    sse = traits.Bool(desc='output sum of squared errors', argstr='--sse')
    cni = File(exists=True, desc='input counfound regressors', argstr='--cni=%s')
    little_bit = traits.Bool(desc='only process small area of brain',
                             argstr='--littlebit')
    gradnonlin = File(exists=True, argstr='--gradnonlin=%s',
                      desc='gradient non linearities')


class DTIFitOutputSpec(TraitedSpec):
    V1 = File(exists=True, desc='path/name of file with the 1st eigenvector')
    V2 = File(exists=True, desc='path/name of file with the 2nd eigenvector')
    V3 = File(exists=True, desc='path/name of file with the 3rd eigenvector')
    L1 = File(exists=True, desc='path/name of file with the 1st eigenvalue')
    L2 = File(exists=True, desc='path/name of file with the 2nd eigenvalue')
    L3 = File(exists=True, desc='path/name of file with the 3rd eigenvalue')
    MD = File(exists=True, desc='path/name of file with the mean diffusivity')
    FA = File(exists=True, desc='path/name of file with the fractional anisotropy')
    MO = File(exists=True, desc='path/name of file with the mode of anisotropy')
    S0 = File(exists=True, desc='path/name of file with the raw T2 signal with no ' +
                                'diffusion weighting')
    tensor = File(exists=True, desc='path/name of file with the 4D tensor volume')
    sse = File(exists=True, desc='path/name of file with the sum squared error')


class DTIFit(FSLCommand):
    """ Use FSL  dtifit command for fitting a diffusion tensor model at each
    voxel
    Example
    -------
    >>> from nipype.interfaces import fsl
    >>> dti = fsl.DTIFit()
    >>> dti.inputs.dwi = 'diffusion.nii'
    >>> dti.inputs.bvecs = 'bvecs'
    >>> dti.inputs.bvals = 'bvals'
    >>> dti.inputs.base_name = 'TP'
    >>> dti.inputs.mask = 'mask.nii'
    >>> dti.cmdline
    'dtifit -k diffusion.nii -o TP -m mask.nii -r bvecs -b bvals'
    """

    _cmd = 'dtifit'
    input_spec = DTIFitInputSpec
    output_spec = DTIFitOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        for k in list(outputs.keys()):
            if k not in ('outputtype', 'environ', 'args'):
                if k != 'tensor' or (isdefined(self.inputs.save_tensor) and
                                     self.inputs.save_tensor):
                    outputs[k] = self._gen_fname(self.inputs.base_name, suffix='_' + k)
        return outputs


class Label2VolInputSpec(FSTraitedSpec):
    seg_file = File(exists=True, desc='segmentation file',
               argstr='--seg %s', mandatory=True)
    template_file = File(exists=True, argstr='--temp %s', mandatory=True,
                         desc='output template volume')
    reg_header = File(exists=True, argstr='--regheader %s',
                      desc='label template volume')
    invert_mtx = traits.Bool(argstr='--invertmtx',
                             desc='Invert the registration matrix')
    fill_thresh = traits.Range(0., 1., argstr='--fillthresh %.f',
                               desc='thresh : between 0 and 1')
    label_voxel_volume = traits.Float(argstr='--labvoxvol %f',
                                      desc='volume of each label point (def 1mm3)')
    proj = traits.Tuple(traits.Enum('abs', 'frac'), traits.Float,
                        traits.Float, traits.Float,
                        argstr='--proj %s %f %f %f',
                        requires=('subject_id', 'hemi'),
                        desc='project along surface normal')
    subject_id = traits.Str(argstr='--subject %s',
                            desc='subject id')
    hemi = traits.Enum('lh', 'rh', argstr='--hemi %s',
                       desc='hemisphere to use lh or rh')
    surface = traits.Str(argstr='--surf %s',
                         desc='use surface instead of white')
    vol_label_file = File(genfile=True, argstr="--o %s", position=-1,
                    desc="final transformation matrix", hash_files=False)
    label_hit_file = File(argstr='--hits %s',
                          desc='file with each frame is nhits for a label')
    map_label_stat = File(argstr='--label-stat %s',
                          desc='map the label stats field into the vol')
    native_vox2ras = traits.Bool(argstr='--native-vox2ras',
                                 desc='use native vox2ras xform instead of  tkregister-style')


class Label2VolOutputSpec(TraitedSpec):
    vol_label_file = File(exists=True, desc='output volume')


class Label2Vol(FSCommand):
    """Make a binary volume from a Freesurfer label
    Examples
    --------
    >>> binvol = Label2Vol(label_file='cortex.label', template_file='structural.nii', reg_file='register.dat', fill_thresh=0.5, vol_label_file='foo_out.nii')
    >>> binvol.cmdline
    'mri_label2vol --fillthresh 0 --label cortex.label --reg register.dat --temp structural.nii --o foo_out.nii'
   """

    _cmd = 'mri_label2vol'
    input_spec = Label2VolInputSpec
    output_spec = Label2VolOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outfile = self.inputs.vol_label_file
        if not isdefined(outfile):
            for key in ['seg_file']:
                if isdefined(getattr(self.inputs, key)):
                    path = getattr(self.inputs, key)
                    if isinstance(path, list):
                        path = path[0]
                    _, src = os.path.split(path)
            outfile = fname_presuffix(src, suffix='_vol.nii.gz',
                                      newpath=os.getcwd(),
                                      use_ext=False)
        outputs['vol_label_file'] = op.abspath(self.inputs.vol_label_file)
        return outputs