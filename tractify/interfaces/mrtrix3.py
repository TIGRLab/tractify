#!/usr/bin/env python

from __future__ import (
    print_function,
    division,
    unicode_literals,
    absolute_import,
)

import os.path as op

from nipype.interfaces.base import traits, TraitedSpec, File, InputMultiObject, Undefined, CommandLineInputSpec, CommandLine, isdefined
from nipype.interfaces.mrtrix3.base import MRTrix3BaseInputSpec, MRTrix3Base


class DWIDenoiseInputSpec(MRTrix3BaseInputSpec):
    in_file = File(
        exists=True,
        argstr="%s",
        position=-2,
        mandatory=True,
        desc="input DWI image",
    )
    mask = File(exists=True, argstr="-mask %s", position=1, desc="mask image")
    extent = traits.Tuple(
        (traits.Int, traits.Int, traits.Int),
        argstr="-extent %d,%d,%d",
        desc="set the window size of the denoising filter. (default = 5,5,5)",
    )
    noise = File(
        argstr="-noise %s",
        name_template="%s_noise",
        name_source=["in_file"],
        keep_extension=True,
        desc="the output noise map",
    )
    out_file = File(
        argstr="%s",
        name_template="%s_denoised",
        name_source=["in_file"],
        keep_extension=True,
        position=-1,
        desc="the output denoised DWI image",
    )


class DWIDenoiseOutputSpec(TraitedSpec):
    out_file = File(desc="the output denoised DWI image", exists=True)
    noise = File(desc="the output noise map (if generated)", exists=True)


class DWIDenoise(MRTrix3Base):
    """
    Denoise DWI data and estimate the noise level based on the optimal
    threshold for PCA.
    DWI data denoising and noise map estimation by exploiting data redundancy
    in the PCA domain using the prior knowledge that the eigenspectrum of
    random covariance matrices is described by the universal Marchenko Pastur
    distribution.
    Important note: image denoising must be performed as the first step of the
    image processing pipeline. The routine will fail if interpolation or
    smoothing has been applied to the data prior to denoising.
    Note that this function does not correct for non-Gaussian noise biases.
    For more information, see
    <https://mrtrix.readthedocs.io/en/latest/reference/commands/dwidenoise.html>
    Example
    -------
    >>> import nipype.interfaces.mrtrix3 as mrt
    >>> denoise = mrt.DWIDenoise()
    >>> denoise.inputs.in_file = 'dwi.mif'
    >>> denoise.inputs.mask = 'mask.mif'
    >>> denoise.cmdline                               # doctest: +ELLIPSIS
    'dwidenoise -mask mask.mif dwi.mif dwi_denoised.mif'
    >>> denoise.run()                                 # doctest: +SKIP
    """

    _cmd = "dwidenoise"
    input_spec = DWIDenoiseInputSpec
    output_spec = DWIDenoiseOutputSpec


class MRDeGibbsInputSpec(MRTrix3BaseInputSpec):
    in_file = File(
        exists=True,
        argstr="%s",
        position=-2,
        mandatory=True,
        desc="input DWI image",
    )
    axes = traits.ListInt(
        default_value=[0, 1],
        usedefault=True,
        sep=",",
        minlen=2,
        maxlen=2,
        argstr="-axes %s",
        desc="indicate the plane in which the data was acquired (axial = 0,1; "
        "coronal = 0,2; sagittal = 1,2",
    )
    nshifts = traits.Int(
        default_value=20,
        usedefault=True,
        argstr="-nshifts %d",
        desc="discretization of subpixel spacing (default = 20)",
    )
    minW = traits.Int(
        default_value=1,
        usedefault=True,
        argstr="-minW %d",
        desc="left border of window used for total variation (TV) computation "
        "(default = 1)",
    )
    maxW = traits.Int(
        default_value=3,
        usedefault=True,
        argstr="-maxW %d",
        desc="right border of window used for total variation (TV) computation "
        "(default = 3)",
    )
    out_file = File(
        name_template="%s_unr",
        name_source="in_file",
        keep_extension=True,
        argstr="%s",
        position=-1,
        desc="the output unringed DWI image",
        genfile=True,
    )


class MRDeGibbsOutputSpec(TraitedSpec):
    out_file = File(desc="the output unringed DWI image", exists=True)


class MRDeGibbs(MRTrix3Base):
    """
    Remove Gibbs ringing artifacts.
    This application attempts to remove Gibbs ringing artefacts from MRI images
    using the method of local subvoxel-shifts proposed by Kellner et al.
    This command is designed to run on data directly after it has been
    reconstructed by the scanner, before any interpolation of any kind has
    taken place. You should not run this command after any form of motion
    correction (e.g. not after dwipreproc). Similarly, if you intend running
    dwidenoise, you should run this command afterwards, since it has the
    potential to alter the noise structure, which would impact on dwidenoise's
    performance.
    Note that this method is designed to work on images acquired with full
    k-space coverage. Running this method on partial Fourier ('half-scan') data
    may lead to suboptimal and/or biased results, as noted in the original
    reference below. There is currently no means of dealing with this; users
    should exercise caution when using this method on partial Fourier data, and
    inspect its output for any obvious artefacts.
    For more information, see
    <https://mrtrix.readthedocs.io/en/latest/reference/commands/mrdegibbs.html>
    Example
    -------
    >>> import nipype.interfaces.mrtrix3 as mrt
    >>> unring = mrt.MRDeGibbs()
    >>> unring.inputs.in_file = 'dwi.mif'
    >>> unring.cmdline
    'mrdegibbs -axes 0,1 -maxW 3 -minW 1 -nshifts 20 dwi.mif dwi_unr.mif'
    >>> unring.run()                                 # doctest: +SKIP
    """

    _cmd = "mrdegibbs"
    input_spec = MRDeGibbsInputSpec
    output_spec = MRDeGibbsOutputSpec


class MRResizeInputSpec(MRTrix3BaseInputSpec):
    in_file = File(
        exists=True,
        argstr="%s",
        position=-2,
        mandatory=True,
        desc="input DWI image",
    )
    size = traits.List(
        traits.Int(),
        argstr="-size %s",
        desc="define the new image size for the output image. This should be "
        "specified as a comma-separated list.",
    )
    voxel_size = traits.List(
        traits.Float(),
        argstr="-voxel %s",
        desc="define the new voxel size for the output image. This can be "
        "specified either as a single value to be used for all "
        "dimensions, or as a comma-separated list of the size for each "
        "voxel dimension.",
    )
    scale = traits.Float(
        argstr="-scale %s",
        desc="scale the image resolution by the supplied factor. This can be "
        "specified either as a single value to be used for all "
        "dimensions, or as a comma-separated list of scale factors for "
        "each dimension.",
    )
    interp = traits.Enum(
        "nearest",
        "linear",
        "cubic",
        "sinc",
        default="cubic",
        argstr="-interp %s",
        desc="set the interpolation method to use when resizing (choices: "
        "nearest, linear, cubic, sinc. Default: cubic).",
    )

    out_file = File(
        argstr="%s",
        name_template="%s_resized",
        name_source=["in_file"],
        keep_extension=True,
        position=-1,
        desc="the output resized DWI image",
    )


class MRResizeOutputSpec(TraitedSpec):
    out_file = File(desc="the output resized DWI image", exists=True)


class MRResize(MRTrix3Base):
    """
    Resize an image by defining the new image resolution, voxel size or a scale factor
    For more information, see
    <https://mrtrix.readthedocs.io/en/latest/reference/commands/mrresize.html>
    Example
    -------
    >>> import nipype.interfaces.mrtrix3 as mrt
    >>> resize = mrt.MRResize()
    >>> resize.inputs.in_file = 'dwi.mif'
    >>> denoise.inputs.mask = 'mask.mif'
    >>> denoise.cmdline                               # doctest: +ELLIPSIS
    'dwidenoise -mask mask.mif dwi.mif dwi_denoised.mif'
    >>> denoise.run()                                 # doctest: +SKIP
    """

    _cmd = "mrresize"
    input_spec = MRResizeInputSpec
    output_spec = MRResizeOutputSpec

class Generate5ttInputSpec(MRTrix3BaseInputSpec):
    algorithm = traits.Enum(
        'fsl',
        'gif',
        'freesurfer',
        argstr='%s',
        position=-3,
        mandatory=True,
        desc='tissue segmentation algorithm')
    in_file = File(
        exists=True,
        argstr='%s',
        mandatory=True,
        position=-2,
        desc='input image')
    out_file = File(
        argstr='%s', mandatory=True, position=-1, desc='output image')


class Generate5ttOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc='output image')


class Generate5tt(MRTrix3Base):
    """
    Generate a 5TT image suitable for ACT using the selected algorithm
    Example
    -------
    >>> import nipype.interfaces.mrtrix3 as mrt
    >>> gen5tt = mrt.Generate5tt()
    >>> gen5tt.inputs.in_file = 'T1.nii.gz'
    >>> gen5tt.inputs.algorithm = 'fsl'
    >>> gen5tt.inputs.out_file = '5tt.mif'
    >>> gen5tt.cmdline                             # doctest: +ELLIPSIS
    '5ttgen fsl T1.nii.gz 5tt.mif'
    >>> gen5tt.run()                               # doctest: +SKIP
    """

    _cmd = '5ttgen'
    input_spec = Generate5ttInputSpec
    output_spec = Generate5ttOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['out_file'] = op.abspath(self.inputs.out_file)
        return outputs

class Generate5ttMaskInputSpec(MRTrix3BaseInputSpec):
    in_file = File(
        exists=True,
        argstr='%s',
        mandatory=True,
        position=-2,
        desc='input image')
    out_file = File(
        argstr='%s', mandatory=True, position=-1, desc='output image')


class Generate5ttMaskOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc='output image')

class Generate5ttMask(MRTrix3Base):
    """
    Generate a 5TT image suitable for ACT using the selected algorithm
    Example
    -------
    >>> import nipype.interfaces.mrtrix3 as mrt
    >>> gen5tt = mrt.Generate5tt()
    >>> gen5tt.inputs.in_file = 'T1.nii.gz'
    >>> gen5tt.inputs.algorithm = 'fsl'
    >>> gen5tt.inputs.out_file = '5tt.mif'
    >>> gen5tt.cmdline                             # doctest: +ELLIPSIS
    '5ttgen fsl T1.nii.gz 5tt.mif'
    >>> gen5tt.run()                               # doctest: +SKIP
    """

    _cmd = '5tt2gmwmi'
    input_spec = Generate5ttMaskInputSpec
    output_spec = Generate5ttMaskOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['out_file'] = op.abspath(self.inputs.out_file)
        return outputs

class ResponseSDInputSpec(MRTrix3BaseInputSpec):
    algorithm = traits.Enum(
        'msmt_5tt',
        'dhollander',
        'tournier',
        'tax',
        argstr='%s',
        position=1,
        mandatory=True,
        desc='response estimation algorithm (multi-tissue)')
    in_file = File(
        exists=True,
        argstr='%s',
        position=-5,
        mandatory=True,
        desc='input DWI image')
    mtt_file = File(argstr='%s', position=-4, desc='input 5tt image')
    wm_file = File(
        'wm.txt',
        argstr='%s',
        position=-3,
        usedefault=True,
        desc='output WM response text file')
    gm_file = File(
        argstr='%s', position=-2, desc='output GM response text file')
    csf_file = File(
        argstr='%s', position=-1, desc='output CSF response text file')
    in_mask = File(
        exists=True, argstr='-mask %s', desc='provide initial mask image')
    max_sh = InputMultiObject(
        traits.Int,
        argstr='-lmax %s',
        sep=',',
        desc=('maximum harmonic degree of response function - single value for '
              'single-shell response, list for multi-shell response'))


class ResponseSDOutputSpec(TraitedSpec):
    wm_file = File(argstr='%s', desc='output WM response text file')
    gm_file = File(argstr='%s', desc='output GM response text file')
    csf_file = File(argstr='%s', desc='output CSF response text file')


class ResponseSD(MRTrix3Base):
    """
    Estimate response function(s) for spherical deconvolution using the specified algorithm.
    Example
    -------
    >>> import nipype.interfaces.mrtrix3 as mrt
    >>> resp = mrt.ResponseSD()
    >>> resp.inputs.in_file = 'dwi.mif'
    >>> resp.inputs.algorithm = 'tournier'
    >>> resp.inputs.grad_fsl = ('bvecs', 'bvals')
    >>> resp.cmdline                               # doctest: +ELLIPSIS
    'dwi2response tournier -fslgrad bvecs bvals dwi.mif wm.txt'
    >>> resp.run()                                 # doctest: +SKIP
    # We can also pass in multiple harmonic degrees in the case of multi-shell
    >>> resp.inputs.max_sh = [6,8,10]
    >>> resp.cmdline
    'dwi2response tournier -fslgrad bvecs bvals -lmax 6,8,10 dwi.mif wm.txt'
    """

    _cmd = 'dwi2response'
    input_spec = ResponseSDInputSpec
    output_spec = ResponseSDOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['wm_file'] = op.abspath(self.inputs.wm_file)
        if self.inputs.gm_file != Undefined:
            outputs['gm_file'] = op.abspath(self.inputs.gm_file)
        if self.inputs.csf_file != Undefined:
            outputs['csf_file'] = op.abspath(self.inputs.csf_file)
        return outputs

class EstimateFODInputSpec(MRTrix3BaseInputSpec):
    algorithm = traits.Enum(
        'csd',
        'msmt_csd',
        argstr='%s',
        position=1,
        mandatory=True,
        desc='FOD algorithm')
    in_file = File(
        exists=True,
        argstr='%s',
        position=2,
        mandatory=True,
        desc='input DWI image')
    wm_txt = File(
        argstr='%s', position=3, mandatory=True, desc='WM response text file')
    wm_odf = File(
        'wm.mif',
        argstr='%s',
        position=-5,
        usedefault=True,
        mandatory=True,
        desc='output WM ODF')
    #gm_txt = File(argstr='%s', position=-4, desc='GM response text file')
    #gm_odf = File('gm.mif', usedefault=True, argstr='%s',
    #              position=-3, desc='output GM ODF')
    #csf_txt = File(argstr='%s', position=-2, desc='CSF response text file')
    #csf_odf = File('csf.mif', usedefault=True, argstr='%s',
    #               position=-1, desc='output CSF ODF')
    mask_file = File(exists=True, argstr='-mask %s', desc='mask image')

    # DW Shell selection options
    shell = traits.List(
        traits.Float,
        sep=',',
        argstr='-shell %s',
        desc='specify one or more dw gradient shells')
    max_sh = traits.Int(
        8, usedefault=True,
        argstr='-lmax %d',
        desc='maximum harmonic degree of response function')
    in_dirs = File(
        exists=True,
        argstr='-directions %s',
        desc=('specify the directions over which to apply the non-negativity '
              'constraint (by default, the built-in 300 direction set is '
              'used). These should be supplied as a text file containing the '
              '[ az el ] pairs for the directions.'))


class EstimateFODOutputSpec(TraitedSpec):
    wm_odf = File(argstr='%s', desc='output WM ODF')
    gm_odf = File(argstr='%s', desc='output GM ODF')
    csf_odf = File(argstr='%s', desc='output CSF ODF')


class EstimateFOD(MRTrix3Base):
    """
    Estimate fibre orientation distributions from diffusion data using spherical deconvolution
    Example
    -------
    >>> import nipype.interfaces.mrtrix3 as mrt
    >>> fod = mrt.EstimateFOD()
    >>> fod.inputs.algorithm = 'csd'
    >>> fod.inputs.in_file = 'dwi.mif'
    >>> fod.inputs.wm_txt = 'wm.txt'
    >>> fod.inputs.grad_fsl = ('bvecs', 'bvals')
    >>> fod.cmdline                               # doctest: +ELLIPSIS
    'dwi2fod -fslgrad bvecs bvals -lmax 8 csd dwi.mif wm.txt wm.mif gm.mif csf.mif'
    >>> fod.run()                                 # doctest: +SKIP
    """

    _cmd = 'dwi2fod'
    input_spec = EstimateFODInputSpec
    output_spec = EstimateFODOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['wm_odf'] = op.abspath(self.inputs.wm_odf)
        #if self.inputs.gm_odf != Undefined:
        #    outputs['gm_odf'] = op.abspath(self.inputs.gm_odf)
        #if self.inputs.csf_odf != Undefined:
        #    outputs['csf_odf'] = op.abspath(self.inputs.csf_odf)
        return outputs

class TractographyInputSpec(MRTrix3BaseInputSpec):
    sph_trait = traits.Tuple(
        traits.Float,
        traits.Float,
        traits.Float,
        traits.Float,
        argstr='%f,%f,%f,%f')

    in_file = File(
        exists=True,
        argstr='%s',
        mandatory=True,
        position=-2,
        desc='input file to be processed')

    out_file = File(
        'tracked.tck',
        argstr='%s',
        mandatory=True,
        position=-1,
        usedefault=True,
        desc='output file containing tracks')

    algorithm = traits.Enum(
        'iFOD2',
        'FACT',
        'iFOD1',
        'Nulldist',
        'SD_Stream',
        'Tensor_Det',
        'Tensor_Prob',
        usedefault=True,
        argstr='-algorithm %s',
        desc='tractography algorithm to be used')

    # ROIs processing options
    roi_incl = traits.Either(
        File(exists=True),
        sph_trait,
        argstr='-include %s',
        desc=('specify an inclusion region of interest, streamlines must'
              ' traverse ALL inclusion regions to be accepted'))
    roi_excl = traits.Either(
        File(exists=True),
        sph_trait,
        argstr='-exclude %s',
        desc=('specify an exclusion region of interest, streamlines that'
              ' enter ANY exclude region will be discarded'))
    roi_mask = traits.Either(
        File(exists=True),
        sph_trait,
        argstr='-mask %s',
        desc=('specify a masking region of interest. If defined,'
              'streamlines exiting the mask will be truncated'))

    # Streamlines tractography options
    step_size = traits.Float(
        argstr='-step %f',
        desc=('set the step size of the algorithm in mm (default is 0.1'
              ' x voxelsize; for iFOD2: 0.5 x voxelsize)'))
    angle = traits.Float(
        argstr='-angle %f',
        desc=('set the maximum angle between successive steps (default '
              'is 90deg x stepsize / voxelsize)'))
    n_tracks = traits.Int(
        argstr='-number %d',
        max_ver='0.4',
        desc=('set the desired number of tracks. The program will continue'
              ' to generate tracks until this number of tracks have been '
              'selected and written to the output file'))
    select = traits.Int(
        argstr='-select %d',
        min_ver='3',
        desc=('set the desired number of tracks. The program will continue'
              ' to generate tracks until this number of tracks have been '
              'selected and written to the output file'))
    max_tracks = traits.Int(
        argstr='-maxnum %d',
        desc=('set the maximum number of tracks to generate. The program '
              'will not generate more tracks than this number, even if '
              'the desired number of tracks hasn\'t yet been reached '
              '(default is 100 x number)'))
    max_length = traits.Float(
        argstr='-maxlength %f',
        desc=('set the maximum length of any track in mm (default is '
              '100 x voxelsize)'))
    min_length = traits.Float(
        argstr='-minlength %f',
        desc=('set the minimum length of any track in mm (default is '
              '5 x voxelsize)'))
    cutoff = traits.Float(
        argstr='-cutoff %f',
        desc=('set the FA or FOD amplitude cutoff for terminating '
              'tracks (default is 0.1)'))
    cutoff_init = traits.Float(
        argstr='-initcutoff %f',
        desc=('set the minimum FA or FOD amplitude for initiating '
              'tracks (default is the same as the normal cutoff)'))
    n_trials = traits.Int(
        argstr='-trials %d',
        desc=('set the maximum number of sampling trials at each point'
              ' (only used for probabilistic tracking)'))
    unidirectional = traits.Bool(
        argstr='-unidirectional',
        desc=('track from the seed point in one direction only '
              '(default is to track in both directions)'))
    init_dir = traits.Tuple(
        traits.Float,
        traits.Float,
        traits.Float,
        argstr='-initdirection %f,%f,%f',
        desc=('specify an initial direction for the tracking (this '
              'should be supplied as a vector of 3 comma-separated values'))
    noprecompt = traits.Bool(
        argstr='-noprecomputed',
        desc=('do NOT pre-compute legendre polynomial values. Warning: this '
              'will slow down the algorithm by a factor of approximately 4'))
    power = traits.Int(
        argstr='-power %d',
        desc=('raise the FOD to the power specified (default is 1/nsamples)'))
    n_samples = traits.Int(
        4, usedefault=True,
        argstr='-samples %d',
        desc=('set the number of FOD samples to take per step for the 2nd '
              'order (iFOD2) method'))
    use_rk4 = traits.Bool(
        argstr='-rk4',
        desc=('use 4th-order Runge-Kutta integration (slower, but eliminates'
              ' curvature overshoot in 1st-order deterministic methods)'))
    stop = traits.Bool(
        argstr='-stop',
        desc=('stop propagating a streamline once it has traversed all '
              'include regions'))
    downsample = traits.Float(
        argstr='-downsample %f',
        desc='downsample the generated streamlines to reduce output file size')

    # Anatomically-Constrained Tractography options
    act_file = File(
        exists=True,
        argstr='-act %s',
        desc=('use the Anatomically-Constrained Tractography framework during'
              ' tracking; provided image must be in the 5TT '
              '(five - tissue - type) format'))
    backtrack = traits.Bool(
        argstr='-backtrack', desc='allow tracks to be truncated')

    crop_at_gmwmi = traits.Bool(
        argstr='-crop_at_gmwmi',
        desc=('crop streamline endpoints more '
              'precisely as they cross the GM-WM interface'))

    # Tractography seeding options
    seed_sphere = traits.Tuple(
        traits.Float,
        traits.Float,
        traits.Float,
        traits.Float,
        argstr='-seed_sphere %f,%f,%f,%f',
        desc='spherical seed')
    seed_image = File(
        exists=True,
        argstr='-seed_image %s',
        desc='seed streamlines entirely at random within mask')
    seed_rnd_voxel = traits.Tuple(
        File(exists=True),
        traits.Int(),
        argstr='-seed_random_per_voxel %s %d',
        xor=['seed_image', 'seed_grid_voxel'],
        desc=('seed a fixed number of streamlines per voxel in a mask '
              'image; random placement of seeds in each voxel'))
    seed_grid_voxel = traits.Tuple(
        File(exists=True),
        traits.Int(),
        argstr='-seed_grid_per_voxel %s %d',
        xor=['seed_image', 'seed_rnd_voxel'],
        desc=('seed a fixed number of streamlines per voxel in a mask '
              'image; place seeds on a 3D mesh grid (grid_size argument '
              'is per axis; so a grid_size of 3 results in 27 seeds per'
              ' voxel)'))
    seed_rejection = File(
        exists=True,
        argstr='-seed_rejection %s',
        desc=('seed from an image using rejection sampling (higher '
              'values = more probable to seed from'))
    seed_gmwmi = File(
        exists=True,
        argstr='-seed_gmwmi %s',
        requires=['act_file'],
        desc=('seed from the grey matter - white matter interface (only '
              'valid if using ACT framework)'))
    seed_dynamic = File(
        exists=True,
        argstr='-seed_dynamic %s',
        desc=('determine seed points dynamically using the SIFT model '
              '(must not provide any other seeding mechanism). Note that'
              ' while this seeding mechanism improves the distribution of'
              ' reconstructed streamlines density, it should NOT be used '
              'as a substitute for the SIFT method itself.'))
    max_seed_attempts = traits.Int(
        argstr='-max_seed_attempts %d',
        desc=('set the maximum number of times that the tracking '
              'algorithm should attempt to find an appropriate tracking'
              ' direction from a given seed point'))
    out_seeds = File(
        'out_seeds.nii.gz', usedefault=True,
        argstr='-output_seeds %s',
        desc=('output the seed location of all successful streamlines to'
              ' a file'))


class TractographyOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc='the output filtered tracks')
    out_seeds = File(
        desc=('output the seed location of all successful'
              ' streamlines to a file'))


class Tractography(MRTrix3Base):
    """
    Performs streamlines tractography after selecting the appropriate
    algorithm.
    .. [FACT] Mori, S.; Crain, B. J.; Chacko, V. P. & van Zijl,
      P. C. M. Three-dimensional tracking of axonal projections in the
      brain by magnetic resonance imaging. Annals of Neurology, 1999,
      45, 265-269
    .. [iFOD1] Tournier, J.-D.; Calamante, F. & Connelly, A. MRtrix:
      Diffusion tractography in crossing fiber regions. Int. J. Imaging
      Syst. Technol., 2012, 22, 53-66
    .. [iFOD2] Tournier, J.-D.; Calamante, F. & Connelly, A. Improved
      probabilistic streamlines tractography by 2nd order integration
      over fibre orientation distributions. Proceedings of the
      International Society for Magnetic Resonance in Medicine, 2010, 1670
    .. [Nulldist] Morris, D. M.; Embleton, K. V. & Parker, G. J.
      Probabilistic fibre tracking: Differentiation of connections from
      chance events. NeuroImage, 2008, 42, 1329-1339
    .. [Tensor_Det] Basser, P. J.; Pajevic, S.; Pierpaoli, C.; Duda, J.
      and Aldroubi, A. In vivo fiber tractography using DT-MRI data.
      Magnetic Resonance in Medicine, 2000, 44, 625-632
    .. [Tensor_Prob] Jones, D. Tractography Gone Wild: Probabilistic Fibre
      Tracking Using the Wild Bootstrap With Diffusion Tensor MRI. IEEE
      Transactions on Medical Imaging, 2008, 27, 1268-1274
    Example
    -------
    >>> import nipype.interfaces.mrtrix3 as mrt
    >>> tk = mrt.Tractography()
    >>> tk.inputs.in_file = 'fods.mif'
    >>> tk.inputs.roi_mask = 'mask.nii.gz'
    >>> tk.inputs.seed_sphere = (80, 100, 70, 10)
    >>> tk.cmdline                               # doctest: +ELLIPSIS
    'tckgen -algorithm iFOD2 -samples 4 -output_seeds out_seeds.nii.gz \
-mask mask.nii.gz -seed_sphere \
80.000000,100.000000,70.000000,10.000000 fods.mif tracked.tck'
    >>> tk.run()                                 # doctest: +SKIP
    """

    _cmd = 'tckgen'
    input_spec = TractographyInputSpec
    output_spec = TractographyOutputSpec

    def _format_arg(self, name, trait_spec, value):
        if 'roi_' in name and isinstance(value, tuple):
            value = ['%f' % v for v in value]
            return trait_spec.argstr % ','.join(value)

        return super(Tractography, self)._format_arg(name, trait_spec, value)

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['out_file'] = op.abspath(self.inputs.out_file)
        return outputs

class TrackSift2InputSpec(MRTrix3BaseInputSpec):
    in_tracks = File(
        exists=True,
        argstr='%s',
        position=1,
        mandatory=True,
        desc='input track file')
    in_fod = File(
        exists=True,
        argstr='%s',
        position=2,
        mandatory=True,
        desc=('input image containing the spherical harmonics of the '
              'fibre orientation distributions'))
    out_weights = File(
        'prob_weights.txt',
        argstr='%s',
        position=3,
        usedefault=True,
        mandatory=True,
        desc=('output text file containing the weighting factor for each'
              'streamline'))

class TrackSift2OutputSpec(TraitedSpec):
    out_weights = File(argstr='%s', desc='output text file containing the weighting factor for each streamline')

class TrackSift2(MRTrix3Base):
    _cmd = 'tcksift2'
    input_spec = TrackSift2InputSpec
    output_spec = TrackSift2OutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['out_weights'] = op.abspath(self.inputs.out_weights)
        return outputs

class BuildConnectomeInputSpec(CommandLineInputSpec):
    in_file = File(
        exists=True,
        argstr='%s',
        mandatory=True,
        position=-3,
        desc='input tractography')
    in_parc = File(
        exists=True, argstr='%s', position=-2, desc='parcellation file')
    out_file = File(
        'connectome.csv',
        argstr='%s',
        mandatory=True,
        position=-1,
        usedefault=True,
        desc='output file after processing')

    nthreads = traits.Int(
        argstr='-nthreads %d',
        desc='number of threads. if zero, the number'
        ' of available cpus will be used',
        nohash=True)

    vox_lookup = traits.Bool(
        argstr='-assignment_voxel_lookup',
        desc='use a simple voxel lookup value at each streamline endpoint')
    search_radius = traits.Float(
        argstr='-assignment_radial_search %f',
        desc='perform a radial search from each streamline endpoint to locate '
        'the nearest node. Argument is the maximum radius in mm; if no node is'
        ' found within this radius, the streamline endpoint is not assigned to'
        ' any node.')
    search_reverse = traits.Float(
        argstr='-assignment_reverse_search %f',
        desc='traverse from each streamline endpoint inwards along the '
        'streamline, in search of the last node traversed by the streamline. '
        'Argument is the maximum traversal length in mm (set to 0 to allow '
        'search to continue to the streamline midpoint).')
    search_forward = traits.Float(
        argstr='-assignment_forward_search %f',
        desc='project the streamline forwards from the endpoint in search of a'
        'parcellation node voxel. Argument is the maximum traversal length in '
        'mm.')

    metric = traits.Enum(
        'count',
        'meanlength',
        'invlength',
        'invnodevolume',
        'mean_scalar',
        'invlength_invnodevolume',
        argstr='-metric %s',
        desc='specify the edge'
        ' weight metric')

    in_scalar = File(
        exists=True,
        argstr='-image %s',
        desc='provide the associated image '
        'for the mean_scalar metric')

    in_weights = File(
        exists=True,
        argstr='-tck_weights_in %s',
        desc='specify a text scalar '
        'file containing the streamline weights')

    keep_unassigned = traits.Bool(
        argstr='-keep_unassigned',
        desc='By default, the program discards the'
        ' information regarding those streamlines that are not successfully '
        'assigned to a node pair. Set this option to keep these values (will '
        'be the first row/column in the output matrix)')

    zero_diagonal = traits.Bool(
        argstr='-zero_diagonal',
        desc='set all diagonal entries in the matrix '
        'to zero (these represent streamlines that connect to the same node at'
        ' both ends)')

    scale_length = traits.Bool(
        argstr='-scale_length',
        desc='scale each contribution to the connectome edge by the length of the'
        'streamline')

    scale_invlength = traits.Bool(
        argstr='-scale_invlength',
        desc='scale each contribution to the connectome edge by the inverse of the'
        'streamline length')

    scale_invnodevol = traits.Bool(
        argstr='-scale_invnodevol',
        desc='scale each contribution to the connectome edge by the inverse of the two'
        'node volumes')

    symmetric = traits.Bool(
        argstr='-symmetric',
        desc='Make matrices symmetric on output')

    stat_edge = traits.Enum(
        'sum',
        'mean',
        'min',
        'max',
        argstr='-stat_edge %s',
        desc='statistic for combining the values from all streamlines in an edge into a'
        'single scale value for that edge (options are: sum,mean,min,max;'
        'default=sum)')


class BuildConnectomeOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc='the output response file')

class BuildConnectome(MRTrix3Base):
    """
    Generate a connectome matrix from a streamlines file and a node
    parcellation image
    Example
    -------
    >>> import nipype.interfaces.mrtrix3 as mrt
    >>> mat = mrt.BuildConnectome()
    >>> mat.inputs.in_file = 'tracks.tck'
    >>> mat.inputs.in_parc = 'aparc+aseg.nii'
    >>> mat.cmdline                               # doctest: +ELLIPSIS
    'tck2connectome tracks.tck aparc+aseg.nii connectome.csv'
    >>> mat.run()                                 # doctest: +SKIP
    """

    _cmd = 'tck2connectome'
    input_spec = BuildConnectomeInputSpec
    output_spec = BuildConnectomeOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['out_file'] = op.abspath(self.inputs.out_file)
        return outputs

class MRConvertInputSpec(CommandLineInputSpec):
    in_file = File(
        exists=True,
        argstr='%s',
        mandatory=True,
        position=-2,
        desc='voxel-order data filename')
    out_filename = File(
        genfile=True, argstr='%s', position=-1, desc='Output filename')
    extract_at_axis = traits.Enum(
        1,
        2,
        3,
        argstr='-coord %s',
        position=1,
        desc=
        '"Extract data only at the coordinates specified. This option specifies the Axis. Must be used in conjunction with extract_at_coordinate.'
    )
    extract_at_coordinate = traits.List(
        traits.Float,
        argstr='%s',
        sep=',',
        position=2,
        minlen=1,
        maxlen=3,
        desc=
        '"Extract data only at the coordinates specified. This option specifies the coordinates. Must be used in conjunction with extract_at_axis. Three comma-separated numbers giving the size of each voxel in mm.'
    )
    voxel_dims = traits.List(
        traits.Float,
        argstr='-vox %s',
        sep=',',
        position=3,
        minlen=3,
        maxlen=3,
        desc=
        'Three comma-separated numbers giving the size of each voxel in mm.')
    output_datatype = traits.Enum(
        "nii",
        "float",
        "char",
        "short",
        "int",
        "long",
        "double",
        argstr='-output %s',
        position=2,
        desc=
        '"i.e. Bfloat". Can be "char", "short", "int", "long", "float" or "double"'
    )  # , usedefault=True)
    extension = traits.Enum(
        "mif",
        "nii",
        "float",
        "char",
        "short",
        "int",
        "long",
        "double",
        position=2,
        desc=
        '"i.e. Bfloat". Can be "char", "short", "int", "long", "float" or "double"',
        usedefault=True)
    layout = traits.Enum(
        "nii",
        "float",
        "char",
        "short",
        "int",
        "long",
        "double",
        argstr='-output %s',
        position=2,
        desc=
        'specify the layout of the data in memory. The actual layout produced will depend on whether the output image format can support it.'
    )
    resample = traits.Float(
        argstr='-scale %d',
        position=3,
        units='mm',
        desc='Apply scaling to the intensity values.')
    offset_bias = traits.Float(
        argstr='-scale %d',
        position=3,
        units='mm',
        desc='Apply offset to the intensity values.')
    replace_NaN_with_zero = traits.Bool(
        argstr='-zero', position=3, desc="Replace all NaN values with zero.")
    prs = traits.Bool(
        argstr='-prs',
        position=3,
        desc=
        "Assume that the DW gradients are specified in the PRS frame (Siemens DICOM only)."
    )


class MRConvertOutputSpec(TraitedSpec):
    converted = File(exists=True, desc='path/name of 4D volume in voxel order')


class MRConvert(CommandLine):
    """
    Perform conversion between different file types and optionally extract a subset of the input image.
    If used correctly, this program can be a very useful workhorse.
    In addition to converting images between different formats, it can
    be used to extract specific studies from a data set, extract a specific
    region of interest, flip the images, or to scale the intensity of the images.
    Example
    -------
    >>> import nipype.interfaces.mrtrix as mrt
    >>> mrconvert = mrt.MRConvert()
    >>> mrconvert.inputs.in_file = 'dwi_FA.mif'
    >>> mrconvert.inputs.out_filename = 'dwi_FA.nii'
    >>> mrconvert.run()                                 # doctest: +SKIP
    """

    _cmd = 'mrconvert'
    input_spec = MRConvertInputSpec
    output_spec = MRConvertOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['converted'] = self.inputs.out_filename
        if not isdefined(outputs['converted']):
            outputs['converted'] = op.abspath(self._gen_outfilename())
        else:
            outputs['converted'] = op.abspath(outputs['converted'])
        return outputs

    def _gen_filename(self, name):
        if name == 'out_filename':
            return self._gen_outfilename()
        else:
            return None

    def _gen_outfilename(self):
        _, name, _ = split_filename(self.inputs.in_file)
        if isdefined(self.inputs.out_filename):
            outname = self.inputs.out_filename
        else:
            outname = name + '_mrconvert.' + self.inputs.extension
        return outname
