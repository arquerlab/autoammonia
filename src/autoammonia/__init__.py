from setuptools import setup

setup(
    name="autoammonia",
    version="0.1.0",
    description="Python library for driving a SDL.",
    author="adpisa",
    packages=["src"], 
    install_requires=[
        "minimalmodbus",
        "numpy",
        "matplotlib",
        "pandas"
    ],
)