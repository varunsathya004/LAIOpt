from setuptools import setup, find_packages

setup(
    name="laiopt",
    version="1.0.0",
    description="LAIOpt - AI-Assisted Chip Layout Optimizer",
    author="LAIOpt Team",
    packages=find_packages(),
    install_requires=[
        "streamlit>=1.28.0",
        "pandas>=2.0.0",
        "matplotlib>=3.7.0",
        "numpy>=1.24.0",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "laiopt=laiopt.frontend.app:main",
        ],
    },
)
