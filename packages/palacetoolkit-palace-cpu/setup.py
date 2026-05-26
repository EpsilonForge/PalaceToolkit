from setuptools import setup
from setuptools.dist import Distribution


class BinaryDistribution(Distribution):
    """Force platform-specific wheel tagging for packaged native binaries."""

    def has_ext_modules(self):
        return True


setup(distclass=BinaryDistribution)
