from setuptools import setup, find_packages

setup(
    name="althtml",
    version="0.1.0",
    author="Varun Bhatnagar",
    author_email="bhatnagarvarun2020@gmail.com",
    description="Python-esque markup language that compiles to html",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=['althtml'],  # This will find all packages automatically
    python_requires=">=3.6",
    install_requires=[
        "watchdog",
        "pyyaml"
        # Add your dependencies here, e.g., "requests>=2.25.1"
    ],
)