from setuptools import setup


with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
	name='TanabeSugano',
	version='0.5',
	packages=['tanabe'],
	install_requires=required,
	url='',
	license='MIT',
	author='hahn',
	author_email='Anselm.Hahn@gmail.com',
	description='A python-solver for Tanabe-Sugano and energy-correlation diagrams',
	platforms=['MacOS :: MacOS X', 'Microsoft :: Windows','POSIX :: Linux']
)
