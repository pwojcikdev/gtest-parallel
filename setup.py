from setuptools import setup

setup(
    name="gtest_parallel",
    version="1.0",
    py_modules=["gtest_parallel"],
    install_requires=[],
    entry_points={
        "console_scripts": [
            "gtest-parallel=gtest_parallel:main",
        ],
    },
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.6",
)
