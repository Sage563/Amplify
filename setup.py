#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="amplify",
    version="1.1.4",
    description="Sound Effects Soundboard with PipeWire/PulseAudio virtual mic routing",
    author="Advik",
    author_email="advikmurthy12@gmail.com",
    url="https://github.com/Sage563/Amplify",
    license="MIT",
    py_modules=["amplify"],
    entry_points={
        'console_scripts': [
            'amplify=amplify:main',
        ],
    },
    install_requires=[
        'PyGObject>=3.42.0',
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: GTK",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Sound/Audio",
    ],
    python_requires=">=3.10",
)
