import setuptools

setuptools.setup(
    name="EDC",
    version="0.1.1",
    author="Adam Webb",
    author_email="adam.webb@lightsource.ca",
    description="Epics Devices for Concert",
    url="https://github.lightsource.ca/BMIT/soft-ioc/",
    packages=["edc"],
    install_requires=["pyepics"],
)
