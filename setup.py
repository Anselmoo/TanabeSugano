try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

__authors__ = ["Anselm Hahn"]
__author_email__ == "Anselm.Hahn@gmail.com"
__license__ = "MIT"
__date__ = "08/09/2019"

with open("requirements.txt") as f:
    required = f.read().splitlines()

setup(
    name="TanabeSugano",
    version="1.1",
    packages=["tanabe", "test"],
    install_requires=required,
    url="https://github.com/Anselmoo/TanabeSugano",
    download_url="https://github.com/Anselmoo/TanabeSugano/releases",
    license=__license__,
    author=__authors__,
    author_email=__author_email__,
    maintainer=__author__,
    maintainer_email=__email__,
    description="A python-solver for Tanabe-Sugano and energy-correlation diagrams",
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
        "Tanabe",
        "Sugano",
        "Tanabe-Sugano",
        "Energy Correlation",
    ],
)
