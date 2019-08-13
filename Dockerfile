FROM poldracklab/fmriprep:1.3.2

# Used command:
# neurodocker generate docker --base=debian:stretch --pkg-manager=apt
# --ants version=latest method=source --mrtrix3 version=3.0_RC3
# --freesurfer version=6.0.0 method=binaries --fsl version=6.0.1 method=binaries

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
        libstdc++6

ARG DEBIAN_FRONTEND="noninteractive"

ENV LANG="en_US.UTF-8" \
    LC_ALL="en_US.UTF-8" \
    ND_ENTRYPOINT="/neurodocker/startup.sh"
RUN export ND_ENTRYPOINT="/neurodocker/startup.sh" \
    && apt-get update -qq \
    && apt-get install -y -q --no-install-recommends \
           apt-utils \
           bzip2 \
           ca-certificates \
           curl \
           locales \
           unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG="en_US.UTF-8" \
    && chmod 777 /opt && chmod a+s /opt \
    && mkdir -p /neurodocker \
    && if [ ! -f "$ND_ENTRYPOINT" ]; then \
         echo '#!/usr/bin/env bash' >> "$ND_ENTRYPOINT" \
    &&   echo 'set -e' >> "$ND_ENTRYPOINT" \
    &&   echo 'export USER="${USER:=`whoami`}"' >> "$ND_ENTRYPOINT" \
    &&   echo 'if [ -n "$1" ]; then "$@"; else /usr/bin/env bash; fi' >> "$ND_ENTRYPOINT"; \
    fi \
    && chmod -R 777 /neurodocker && chmod a+s /neurodocker

ENTRYPOINT ["/neurodocker/startup.sh"]

# ANTS
# from https://github.com/kaczmarj/ANTs-builds/blob/master/Dockerfile

# Get CMake for ANTS
RUN mkdir /cmake_temp
WORKDIR /cmake_temp
RUN wget https://cmake.org/files/v3.12/cmake-3.12.2.tar.gz \
    && tar -xzvf cmake-3.12.2.tar.gz \
    && echo 'done tar' \
    && ls \
    && cd cmake-3.12.2/ \
    && ./bootstrap -- -DCMAKE_BUILD_TYPE:STRING=Release \
    && make -j4 \
    && make install \
    && cd .. \
    && rm -rf *

RUN cmake --version

RUN mkdir /ants
RUN apt-get update && apt-get -y install zlib1g-dev

RUN git clone https://github.com/ANTsX/ANTs.git --branch v2.3.1 /ants
WORKDIR /ants

RUN mkdir build \
    && cd build \
    && git config --global url."https://".insteadOf git:// \
    && cmake .. \
    && make -j1 \
    && mkdir -p /opt/ants \
    && mv bin/* /opt/ants && mv ../Scripts/* /opt/ants \
    && cd .. \
    && rm -rf build

ENV ANTSPATH=/opt/ants/ \
    PATH=/opt/ants:$PATH

WORKDIR /

# FSL from neurodocker
ENV FSLDIR="/opt/fsl-6.0.1" \
    PATH="/opt/fsl-6.0.1/bin:$PATH"
RUN apt-get update -qq \
    && apt-get install -y -q --no-install-recommends \
           bc \
           dc \
           file \
           libfontconfig1 \
           libfreetype6 \
           libgl1-mesa-dev \
           libglu1-mesa-dev \
           libgomp1 \
           libice6 \
           libxcursor1 \
           libxft2 \
           libxinerama1 \
           libxrandr2 \
           libxrender1 \
           libxt6 \
           wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && echo "Downloading FSL ..." \
    && mkdir -p /opt/fsl-6.0.1 \
    && curl -fsSL --retry 5 https://fsl.fmrib.ox.ac.uk/fsldownloads/fsl-6.0.1-centos6_64.tar.gz \
    | tar -xz -C /opt/fsl-6.0.1 --strip-components 1 \
    && sed -i '$iecho Some packages in this Docker container are non-free' $ND_ENTRYPOINT \
    && sed -i '$iecho If you are considering commercial use of this container, please consult the relevant license:' $ND_ENTRYPOINT \
    && sed -i '$iecho https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Licence' $ND_ENTRYPOINT \
    && sed -i '$isource $FSLDIR/etc/fslconf/fsl.sh' $ND_ENTRYPOINT

RUN echo '{ \
    \n  "pkg_manager": "apt", \
    \n  "instructions": [ \
    \n    [ \
    \n      "base", \
    \n      "poldracklab/fmriprep:1.3.2" \
    \n    ], \
    \n    [ \
    \n      "fsl", \
    \n      { \
    \n        "version": "6.0.1", \
    \n        "method": "binaries" \
    \n      } \
    \n    ] \
    \n  ] \
    \n}' > /neurodocker/neurodocker_specs.json

# FSL 6.0.1
# Freesurfer 6.0.0
# MRtrix3
# ANTS
# Python 3

# MRtrix3
# from https://hub.docker.com/r/neurology/mrtrix/dockerfile
RUN apt-get update
RUN apt-get install -y --no-install-recommends \
    python \
    python-numpy \
    libeigen3-dev \
    clang \
    zlib1g-dev \
    libqt4-opengl-dev \
    libgl1-mesa-dev \
    git \
    ca-certificates
RUN mkdir /mrtrix
RUN git clone https://github.com/MRtrix3/mrtrix3.git --branch 3.0_RC3 /mrtrix
WORKDIR /mrtrix
# Checkout version used in the lab: 20180128
RUN git checkout f098f097ccbb3e5efbb8f5552f13e0997d161cce
ENV CXX=/usr/bin/clang++
RUN ./configure
RUN ./build
RUN ./set_path
ENV PATH=/mrtrix/bin:$PATH

WORKDIR /

# add credentials on build
RUN mkdir ~/.ssh && ln -s /run/secrets/host_ssh_key ~/.ssh/id_rsa
# Getting required installation tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libopenblas-base

# setting up an install of tractify (manual version) inside the container
#ADD https://api.github.com/repos/TIGRLab/tractify/git/refs/heads/master version.json
#RUN git clone -b master https://github.com/TIGRLab/tractify.git tractify
# Following two lines assumes you are building from within a pulled tractify repo
RUN mkdir tractify
COPY ./ tractify/
RUN pip install --upgrade pip
RUN pip install \
    numba==0.45.0 \
    Click==7.0 \
    dipy==0.16.0 \
    pybids==0.9.2 \
    nipype==1.2.0 \
    niworkflows==0.10.2
RUN cd tractify && python setup.py install

ENTRYPOINT ["tractify"]
