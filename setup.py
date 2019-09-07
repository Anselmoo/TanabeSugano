from setuptools import setup

import os


with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
	name='TanabeSugano',
	version='0.5',
	packages=['src'],
	install_requires=required,
	url='',
	license='MIT',
	author='hahn',
	author_email='Anselm.Hahn@gmail.com',
	description='A python-solver for Tanabe-Sugano and energy-correlation diagrams'
)
