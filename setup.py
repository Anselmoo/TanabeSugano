try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

__authors__ = ['Anselm Hahn']
__license__ = 'MIT'
__date__ = '08/09/2019'

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
	name='TanabeSugano',
	version='1.0',
	packages=['tanabe','test'],
	install_requires=required,
	url='https://github.com/Anselmoo/TanabeSugano',
	download_url='https://github.com/Anselmoo/TanabeSugano/releases',
	license=__license__,
	author=__authors__,
	author_email='Anselm.Hahn@gmail.com',
	description='A python-solver for Tanabe-Sugano and energy-correlation diagrams',
	platforms=['MacOS :: MacOS X', 'Microsoft :: Windows','POSIX :: Linux'],
)
