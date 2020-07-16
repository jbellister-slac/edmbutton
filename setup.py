"""Setup module for edmbutton"""

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='edmbutton',
    version='0.3.1',
    description='A PyDM widget for launching EDM displays.',
    long_description=long_description,
    author='Matt Gibbs',
    author_email='mgibbs@slac.stanford.edu',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 2.7',
    ],

    keywords='pydm edm',
    packages=find_packages(exclude=['contrib', 'doc', 'tests']),
    install_requires=['pydm'],
)
