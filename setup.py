#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    "Click>=6.0",
    "nipype>=1.2.2",
    "dipy",
    "numba",
    "pybids>=0.9.4",
    "niworkflows>=0.10.3rc1"
]

setup_requirements = [ ]

test_requirements = [ ]

setup(
    author="Salim Mansour",
    author_email='Salim.Mansour@camh.ca',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    description="Tractography pipeline",
    entry_points={
        'console_scripts': [
            'tractify=tractify.cli:main',
        ],
    },
    install_requires=requirements,
    license="MIT license",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='tractify',
    name='tractify',
    packages=find_packages(include=['tractify*']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/TIGRLab/tractify',
    version='0.1.0',
    zip_safe=False,
)
