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

class InvWarpInputSpec(FSLCommandInputSpec):
    warp = File(exists=True, argstr='--warp=%s', mandatory=True,
                desc=('Name of file containing warp-coefficients/fields. This '
                      'would typically be the output from the --cout switch of '
                      'fnirt (but can also use fields, like the output from '
                      '--fout).'))
    reference = File(exists=True, argstr='--ref=%s', mandatory=True,
                     desc=('Name of a file in target space. Note that the '
                           'target space is now different from the target '
                           'space that was used to create the --warp file. It '
                           'would typically be the file that was specified '
                           'with the --in argument when running fnirt.'))
    inverse_warp = File(argstr='--out=%s', name_source=['warp'],
                        hash_files=False, name_template='%s_inverse',
                        desc=('Name of output file, containing warps that are '
                              'the "reverse" of those in --warp. This will be '
                              'a field-file (rather than a file of spline '
                              'coefficients), and it will have any affine '
                              'component included as part of the '
                              'displacements.'))
    absolute = traits.Bool(argstr='--abs', xor=['relative'],
                           desc=('If set it indicates that the warps in --warp '
                                 'should be interpreted as absolute, provided '
                                 'that it is not created by fnirt (which '
                                 'always uses relative warps). If set it also '
                                 'indicates that the output --out should be '
                                 'absolute.'))
    relative = traits.Bool(argstr='--rel', xor=['absolute'],
                           desc=('If set it indicates that the warps in --warp '
                                 'should be interpreted as relative. I.e. the '
                                 'values in --warp are displacements from the '
                                 'coordinates in the --ref space. If set it '
                                 'also indicates that the output --out should '
                                 'be relative.'))
    niter = traits.Int(argstr='--niter=%d',
                       desc=('Determines how many iterations of the '
                             'gradient-descent search that should be run.'))
    regularise = traits.Float(argstr='--regularise=%f',
                              desc='Regularization strength (deafult=1.0).')
    noconstraint = traits.Bool(argstr='--noconstraint',
                               desc='Do not apply Jacobian constraint')
    jacobian_min = traits.Float(argstr='--jmin=%f',
                                desc=('Minimum acceptable Jacobian value for '
                                      'constraint (default 0.01)'))
    jacobian_max = traits.Float(argstr='--jmax=%f',
                                desc=('Maximum acceptable Jacobian value for '
                                      'constraint (default 100.0)'))


class InvWarpOutputSpec(TraitedSpec):
    inverse_warp = File(exists=True,
                        desc=('Name of output file, containing warps that are '
                              'the "reverse" of those in --warp.'))


class InvWarp(FSLCommand):
    """
    Use FSL Invwarp to invert a FNIRT warp


    Examples
    --------

    >>> from nipype.interfaces.fsl import InvWarp
    >>> invwarp = InvWarp()
    >>> invwarp.inputs.warp = "struct2mni.nii"
    >>> invwarp.inputs.reference = "anatomical.nii"
    >>> invwarp.inputs.output_type = "NIFTI_GZ"
    >>> invwarp.cmdline
    'invwarp --out=struct2mni_inverse.nii.gz --ref=anatomical.nii --warp=struct2mni.nii'
    >>> res = invwarp.run() # doctest: +SKIP


    """

    input_spec = InvWarpInputSpec
    output_spec = InvWarpOutputSpec

    _cmd = 'invwarp'



class FNIRTInputSpec(FSLCommandInputSpec):
    ref_file = File(exists=True, argstr='--ref=%s', mandatory=True,
                    desc='name of reference image')
    in_file = File(exists=True, argstr='--in=%s', mandatory=True,
                   desc='name of input image')
    affine_file = File(exists=True, argstr='--aff=%s',
                       desc='name of file containing affine transform')
    inwarp_file = File(exists=True, argstr='--inwarp=%s',
                       desc='name of file containing initial non-linear warps')
    in_intensitymap_file = File(exists=True, argstr='--intin=%s',
                                desc='name of file/files containing initial intensity maping'
                                'usually generated by previos fnirt run')
    fieldcoeff_file = traits.Either(traits.Bool, File, argstr='--cout=%s',
                                    desc='name of output file with field coefficients or true')
    warped_file = File(argstr='--iout=%s',
                       desc='name of output image', genfile=True, hash_files=False)
    field_file = traits.Either(traits.Bool, File,
                               argstr='--fout=%s',
                               desc='name of output file with field or true', hash_files=False)
    jacobian_file = traits.Either(traits.Bool, File,
                                  argstr='--jout=%s',
                                  desc='name of file for writing out the Jacobian'
                                  'of the field (for diagnostic or VBM purposes)', hash_files=False)
    modulatedref_file = traits.Either(traits.Bool, File,
                                      argstr='--refout=%s',
                                      desc='name of file for writing out intensity modulated'
                                      '--ref (for diagnostic purposes)', hash_files=False)
    out_intensitymap_file = traits.Either(traits.Bool, File,
                                          argstr='--intout=%s',
                                          desc='name of files for writing information pertaining '
                                          'to intensity mapping', hash_files=False)
    log_file = File(argstr='--logout=%s',
                    desc='Name of log-file', genfile=True, hash_files=False)
    config_file = traits.Either(
        traits.Enum("T1_2_MNI152_2mm", "FA_2_FMRIB58_1mm"), File(exists=True), argstr='--config=%s',
        desc='Name of config file specifying command line arguments')
    refmask_file = File(exists=True, argstr='--refmask=%s',
                        desc='name of file with mask in reference space')
    inmask_file = File(exists=True, argstr='--inmask=%s',
                       desc='name of file with mask in input image space')
    skip_refmask = traits.Bool(
        argstr='--applyrefmask=0', xor=['apply_refmask'],
        desc='Skip specified refmask if set, default false')
    skip_inmask = traits.Bool(argstr='--applyinmask=0', xor=['apply_inmask'],
                              desc='skip specified inmask if set, default false')
    apply_refmask = traits.List(
        traits.Enum(0, 1), argstr='--applyrefmask=%s', xor=['skip_refmask'],
        desc='list of iterations to use reference mask on (1 to use, 0 to skip)', sep=",")
    apply_inmask = traits.List(
        traits.Enum(0, 1), argstr='--applyinmask=%s', xor=['skip_inmask'],
        desc='list of iterations to use input mask on (1 to use, 0 to skip)', sep=",")
    skip_implicit_ref_masking = traits.Bool(argstr='--imprefm=0',
                                            desc='skip implicit masking  based on value'
                                            'in --ref image. Default = 0')
    skip_implicit_in_masking = traits.Bool(argstr='--impinm=0',
                                           desc='skip implicit masking  based on value'
                                           'in --in image. Default = 0')
    refmask_val = traits.Float(argstr='--imprefval=%f',
                               desc='Value to mask out in --ref image. Default =0.0')
    inmask_val = traits.Float(argstr='--impinval=%f',
                              desc='Value to mask out in --in image. Default =0.0')
    max_nonlin_iter = traits.List(traits.Int,
                                  argstr='--miter=%s',
                                  desc='Max # of non-linear iterations list, default [5, 5, 5, 5]', sep=",")
    subsampling_scheme = traits.List(traits.Int,
                                     argstr='--subsamp=%s',
                                     desc='sub-sampling scheme, list, default [4, 2, 1, 1]',
                                     sep=",")
    warp_resolution = traits.Tuple(traits.Int, traits.Int, traits.Int,
                                   argstr='--warpres=%d,%d,%d',
                                   desc='(approximate) resolution (in mm) of warp basis '
                                   'in x-, y- and z-direction, default 10, 10, 10')
    spline_order = traits.Int(argstr='--splineorder=%d',
                              desc='Order of spline, 2->Qadratic spline, 3->Cubic spline. Default=3')
    in_fwhm = traits.List(traits.Int, argstr='--infwhm=%s',
                          desc='FWHM (in mm) of gaussian smoothing kernel for input volume, default [6, 4, 2, 2]', sep=",")
    ref_fwhm = traits.List(traits.Int, argstr='--reffwhm=%s',
                           desc='FWHM (in mm) of gaussian smoothing kernel for ref volume, default [4, 2, 0, 0]', sep=",")
    regularization_model = traits.Enum('membrane_energy', 'bending_energy',
                                       argstr='--regmod=%s',
                                       desc='Model for regularisation of warp-field [membrane_energy bending_energy], default bending_energy')
    regularization_lambda = traits.List(traits.Float, argstr='--lambda=%s',
                                        desc='Weight of regularisation, default depending on --ssqlambda and --regmod '
                                        'switches. See user documetation.', sep=",")
    skip_lambda_ssq = traits.Bool(argstr='--ssqlambda=0',
                                  desc='If true, lambda is not weighted by current ssq, default false')
    jacobian_range = traits.Tuple(traits.Float, traits.Float,
                                  argstr='--jacrange=%f,%f',
                                  desc='Allowed range of Jacobian determinants, default 0.01, 100.0')
    derive_from_ref = traits.Bool(argstr='--refderiv',
                                  desc='If true, ref image is used to calculate derivatives. Default false')
    intensity_mapping_model = traits.Enum('none', 'global_linear', 'global_non_linear'
                                          'local_linear', 'global_non_linear_with_bias',
                                          'local_non_linear', argstr='--intmod=%s',
                                          desc='Model for intensity-mapping')
    intensity_mapping_order = traits.Int(argstr='--intorder=%d',
                                         desc='Order of poynomial for mapping intensities, default 5')
    biasfield_resolution = traits.Tuple(traits.Int, traits.Int, traits.Int,
                                        argstr='--biasres=%d,%d,%d',
                                        desc='Resolution (in mm) of bias-field modelling '
                                        'local intensities, default 50, 50, 50')
    bias_regularization_lambda = traits.Float(argstr='--biaslambda=%f',
                                              desc='Weight of regularisation for bias-field, default 10000')
    skip_intensity_mapping = traits.Bool(
        argstr='--estint=0', xor=['apply_intensity_mapping'],
        desc='Skip estimate intensity-mapping default false')
    apply_intensity_mapping = traits.List(
        traits.Enum(0, 1), argstr='--estint=%s', xor=['skip_intensity_mapping'],
        desc='List of subsampling levels to apply intensity mapping for (0 to skip, 1 to apply)', sep=",")
    hessian_precision = traits.Enum('double', 'float', argstr='--numprec=%s',
                                    desc='Precision for representing Hessian, double or float. Default double')


class FNIRTOutputSpec(TraitedSpec):
    fieldcoeff_file = File(exists=True, desc='file with field coefficients')
    warped_file = File(exists=True, desc='warped image')
    field_file = File(desc='file with warp field')
    jacobian_file = File(desc='file containing Jacobian of the field')
    modulatedref_file = File(desc='file containing intensity modulated --ref')
    out_intensitymap_file = File(
        desc='file containing info pertaining to intensity mapping')
    log_file = File(desc='Name of log-file')


class FNIRT(FSLCommand):
    """Use FSL FNIRT for non-linear registration.

    Examples
    --------
    >>> from nipype.interfaces import fsl
    >>> from nipype.testing import example_data
    >>> fnt = fsl.FNIRT(affine_file=example_data('trans.mat'))
    >>> res = fnt.run(ref_file=example_data('mni.nii', in_file=example_data('structural.nii')) #doctest: +SKIP

    T1 -> Mni153

    >>> from nipype.interfaces import fsl
    >>> fnirt_mprage = fsl.FNIRT()
    >>> fnirt_mprage.inputs.in_fwhm = [8, 4, 2, 2]
    >>> fnirt_mprage.inputs.subsampling_scheme = [4, 2, 1, 1]

    Specify the resolution of the warps

    >>> fnirt_mprage.inputs.warp_resolution = (6, 6, 6)
    >>> res = fnirt_mprage.run(in_file='structural.nii', ref_file='mni.nii', warped_file='warped.nii', fieldcoeff_file='fieldcoeff.nii')#doctest: +SKIP

    We can check the command line and confirm that it's what we expect.

    >>> fnirt_mprage.cmdline  #doctest: +SKIP
    'fnirt --cout=fieldcoeff.nii --in=structural.nii --infwhm=8,4,2,2 --ref=mni.nii --subsamp=4,2,1,1 --warpres=6,6,6 --iout=warped.nii'

    """

    _cmd = 'fnirt'
    input_spec = FNIRTInputSpec
    output_spec = FNIRTOutputSpec

    filemap = {'warped_file': 'warped',
               'field_file': 'field',
               'jacobian_file': 'field_jacobian',
               'modulatedref_file': 'modulated',
               'out_intensitymap_file': 'intmap',
               'log_file': 'log.txt',
               'fieldcoeff_file': 'fieldwarp'}

    def _list_outputs(self):
        outputs = self.output_spec().get()
        for key, suffix in list(self.filemap.items()):
            inval = getattr(self.inputs, key)
            change_ext = True
            if key in ['warped_file', 'log_file']:
                if suffix.endswith('.txt'):
                    change_ext = False
                if isdefined(inval):
                    outputs[key] = inval
                else:
                    outputs[key] = self._gen_fname(self.inputs.in_file,
                                                   suffix='_' + suffix,
                                                   change_ext=change_ext)
            elif isdefined(inval):
                if isinstance(inval, bool):
                    if inval:
                        outputs[key] = self._gen_fname(self.inputs.in_file,
                                                       suffix='_' + suffix,
                                                       change_ext=change_ext)
                else:
                    outputs[key] = os.path.abspath(inval)
        return outputs

    def _format_arg(self, name, spec, value):
        if name in list(self.filemap.keys()):
            return spec.argstr % self._list_outputs()[name]
        return super(FNIRT, self)._format_arg(name, spec, value)

    def _gen_filename(self, name):
        if name in ['warped_file', 'log_file']:
            return self._list_outputs()[name]
        return None

    def write_config(self, configfile):
        """Writes out currently set options to specified config file

        XX TODO : need to figure out how the config file is written

        Parameters
        ----------
        configfile : /path/to/configfile
        """
        try:
            fid = open(configfile, 'w+')
        except IOError:
            print ('unable to create config_file %s' % (configfile))

        for item in list(self.inputs.get().items()):
            fid.write('%s\n' % (item))
        fid.close()



class ApplyWarpInputSpec(FSLCommandInputSpec):
    in_file = File(exists=True, argstr='--in=%s',
                   mandatory=True, position=0,
                   desc='image to be warped')
    out_file = File(argstr='--out=%s', genfile=True, position=2,
                    desc='output filename', hash_files=False)
    ref_file = File(exists=True, argstr='--ref=%s',
                    mandatory=True, position=1,
                    desc='reference image')
    field_file = File(exists=True, argstr='--warp=%s',
                      desc='file containing warp field')
    abswarp = traits.Bool(argstr='--abs', xor=['relwarp'],
                          desc="treat warp field as absolute: x' = w(x)")
    relwarp = traits.Bool(argstr='--rel', xor=['abswarp'], position=-1,
                          desc="treat warp field as relative: x' = x + w(x)")
    datatype = traits.Enum('char', 'short', 'int', 'float', 'double',
                           argstr='--datatype=%s',
                           desc='Force output data type [char short int float double].')
    supersample = traits.Bool(argstr='--super',
                              desc='intermediary supersampling of output, default is off')
    superlevel = traits.Either(traits.Enum('a'), traits.Int,
                               argstr='--superlevel=%s',
                               desc="level of intermediary supersampling, a for 'automatic' or integer level. Default = 2")
    premat = File(exists=True, argstr='--premat=%s',
                  desc='filename for pre-transform (affine matrix)')
    postmat = File(exists=True, argstr='--postmat=%s',
                   desc='filename for post-transform (affine matrix)')
    mask_file = File(exists=True, argstr='--mask=%s',
                     desc='filename for mask image (in reference space)')
    interp = traits.Enum(
        'nn', 'trilinear', 'sinc', 'spline', argstr='--interp=%s', position=-2,
        desc='interpolation method')


class ApplyWarpOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc='Warped output file')


class ApplyWarp(FSLCommand):
    """Use FSL's applywarp to apply the results of a FNIRT registration

    Examples
    --------
    >>> from nipype.interfaces import fsl
    >>> from nipype.testing import example_data
    >>> aw = fsl.ApplyWarp()
    >>> aw.inputs.in_file = example_data('structural.nii')
    >>> aw.inputs.ref_file = example_data('mni.nii')
    >>> aw.inputs.field_file = 'my_coefficients_filed.nii' #doctest: +SKIP
    >>> res = aw.run() #doctest: +SKIP


    """

    _cmd = 'applywarp'
    input_spec = ApplyWarpInputSpec
    output_spec = ApplyWarpOutputSpec

    def _format_arg(self, name, spec, value):
        if name == 'superlevel':
            return spec.argstr % str(value)
        return super(ApplyWarp, self)._format_arg(name, spec, value)

    def _list_outputs(self):
        outputs = self._outputs().get()
        if not isdefined(self.inputs.out_file):
            outputs['out_file'] = self._gen_fname(self.inputs.in_file,
                                                  suffix='_warp')
        else:
            outputs['out_file'] = os.path.abspath(self.inputs.out_file)
        return outputs

    def _gen_filename(self, name):
        if name == 'out_file':
            return self._list_outputs()[name]
        return None



class Reorient2StdInputSpec(FSLCommandInputSpec):
    in_file = File(exists=True, mandatory=True, argstr="%s")
    out_file = File(genfile=True, hash_files=False, argstr="%s")


class Reorient2StdOutputSpec(TraitedSpec):
    out_file = File(exists=True)


class Reorient2Std(FSLCommand):
    """fslreorient2std is a tool for reorienting the image to match the
    approximate orientation of the standard template images (MNI152).


    Examples
    --------

    >>> reorient = Reorient2Std()
    >>> reorient.inputs.in_file = "functional.nii"
    >>> res = reorient.run() # doctest: +SKIP


    """
    _cmd = 'fslreorient2std'
    input_spec = Reorient2StdInputSpec
    output_spec = Reorient2StdOutputSpec

    def _gen_filename(self, name):
        if name == 'out_file':
            return self._gen_fname(self.inputs.in_file,
                                   suffix="_reoriented")
        return None

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if not isdefined(self.inputs.out_file):
            outputs['out_file'] = self._gen_filename('out_file')
        else:
            outputs['out_file'] = os.path.abspath(self.inputs.out_file)
        return outputs



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