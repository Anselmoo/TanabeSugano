try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

__authors__ = ["Anselm Hahn"]
__author_email__ = "Anselm.Hahn@gmail.com"
__license__ = "MIT"
__date__ = "08/09/2019"

with open("requirements.txt") as f:
    required = f.read().splitlines()

with open("README.md") as f:
    long_description = f.read()

setup(
    name="TanabeSugano",
    description="A python-solver for Tanabe-Sugano and Energy-Correlation diagrams",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version="1.1.2",
    packages=setuptools.find_packages(),
    install_requires=required,
    url="https://github.com/Anselmoo/TanabeSugano",
    download_url="https://github.com/Anselmoo/TanabeSugano/releases",
    license=__license__,
    author=__authors__,
    author_email=__author_email__,
    maintainer=__authors__,
    maintainer_email=__author_email__,
    platforms=["MacOS :: MacOS X", "Microsoft :: Windows", "POSIX :: Linux"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Education",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
        "Operating System :: Unix",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: System :: Shells",
        "Topic :: Scientific/Engineering :: Visualization",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Utilities",
    ],
    keywords=[
        "terminal",
        "data-visualization",
        "tanabe",
        "sugano",
        "tanabe-sugano",
        "energy-correlation",
        "complex-ions",
    ],
)
