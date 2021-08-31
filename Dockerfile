FROM ubuntu:xenial-20210722

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bc \
        libtool \
        tar \
        dpkg \
        curl \
        wget \
        unzip \
        gcc \
        git \
        libstdc++6 \
        python \
        ca-certificates \
        libeigen3-dev \
        clang \
        zlib1g-dev \
        libqt4-opengl-dev \
        libgl1-mesa-dev \
        libopenblas-base

# Build FSL in container
ENV FSLDIR="/opt/fsl-6.0.1" \
    PATH="/opt/fsl-6.0.1/bin:$PATH" \
    FSLOUTPUTTYPE="NIFTI_GZ"
RUN echo "Downloading FSL ..." \
    && wget -q http://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py \
    && chmod 775 fslinstaller.py
RUN /fslinstaller.py -d /opt/fsl-6.0.1 -V 6.0.1 -q

# MRtrix3
# from https://hub.docker.com/r/neurology/mrtrix/dockerfile
RUN mkdir /mrtrix
RUN git clone https://github.com/MRtrix3/mrtrix3.git --branch 3.0.2 /mrtrix
WORKDIR /mrtrix
# Checkout version used in the lab: 20180128
# RUN git checkout f098f097ccbb3e5efbb8f5552f13e0997d161cce
ENV CXX=/usr/bin/clang++
RUN ./configure
RUN ./build
RUN ./set_path
ENV PATH=/mrtrix/bin:$PATH

WORKDIR /

# Installing freesurfer
RUN curl -sSL https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.1.0/freesurfer-linux-centos8_x86_64-7.1.0.tar.gz \
    | tar zxv --no-same-owner -C /opt \
    --exclude='freesurfer/diffusion' \
    --exclude='freesurfer/docs' \
    --exclude='freesurfer/fsfast' \
    --exclude='freesurfer/lib/cuda' \
    --exclude='freesurfer/lib/qt' \
    --exclude='freesurfer/matlab' \
    --exclude='freesurfer/mni/share/man' \
    --exclude='freesurfer/subjects/fsaverage_sym' \
    --exclude='freesurfer/subjects/fsaverage3' \
    --exclude='freesurfer/subjects/fsaverage4' \
    --exclude='freesurfer/subjects/cvs_avg35' \
    --exclude='freesurfer/subjects/cvs_avg35_inMNI152' \
    --exclude='freesurfer/subjects/bert' \
    --exclude='freesurfer/subjects/lh.EC_average' \
    --exclude='freesurfer/subjects/rh.EC_average' \
    --exclude='freesurfer/subjects/sample-*.mgz' \
    --exclude='freesurfer/subjects/V1_average' \
    --exclude='freesurfer/trctrain'

# Simulate SetUpFreeSurfer.sh
ENV FSL_DIR="/opt/fsl-6.0.1" \
    OS="Linux" \
    FS_OVERRIDE=0 \
    FIX_VERTEX_AREA="" \
    FSF_OUTPUT_FORMAT="nii.gz" \
    FREESURFER_HOME="/opt/freesurfer"
ENV SUBJECTS_DIR="$FREESURFER_HOME/subjects" \
    FUNCTIONALS_DIR="$FREESURFER_HOME/sessions" \
    MNI_DIR="$FREESURFER_HOME/mni" \
    LOCAL_DIR="$FREESURFER_HOME/local" \
    MINC_BIN_DIR="$FREESURFER_HOME/mni/bin" \
    MINC_LIB_DIR="$FREESURFER_HOME/mni/lib" \
    MNI_DATAPATH="$FREESURFER_HOME/mni/data"
ENV PERL5LIB="$MINC_LIB_DIR/perl5/5.8.5" \
    MNI_PERL5LIB="$MINC_LIB_DIR/perl5/5.8.5" \
    PATH="$FREESURFER_HOME/bin:$FSFAST_HOME/bin:$FREESURFER_HOME/tktools:$MINC_BIN_DIR:$PATH"

# Installing and setting up miniconda
RUN curl -sSLO https://repo.continuum.io/miniconda/Miniconda3-4.5.11-Linux-x86_64.sh && \
    bash Miniconda3-4.5.11-Linux-x86_64.sh -b -p /usr/local/miniconda && \
    rm Miniconda3-4.5.11-Linux-x86_64.sh

# Set CPATH for packages relying on compiled libs (e.g. indexed_gzip)
ENV PATH="/usr/local/miniconda/bin:$PATH" \
    CPATH="/usr/local/miniconda/include/:$CPATH" \
    LANG="C.UTF-8" \
    LC_ALL="C.UTF-8" \
    PYTHONNOUSERSITE=1

# Add credentials on build
RUN mkdir ~/.ssh && ln -s /run/secrets/host_ssh_key ~/.ssh/id_rsa

RUN conda install -y python=3.7.3 \
                     pip=19.1 \
                     libxml2=2.9.8 \
                     libxslt=1.1.32 \
                     graphviz=2.40.1; sync && \
    chmod -R a+rX /usr/local/miniconda; sync && \
    chmod +x /usr/local/miniconda/bin/*; sync && \
    conda build purge-all; sync && \
    conda clean -tipsy && sync

RUN pip install --upgrade pip

RUN mkdir tractify
COPY ./ tractify/
RUN cd tractify && pip install .

ENTRYPOINT ["tractify"]

