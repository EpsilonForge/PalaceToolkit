from setuptools import setup
from setuptools.dist import Distribution
from wheel.bdist_wheel import bdist_wheel


class BinaryDistribution(Distribution):
    """Force platform-specific wheel tagging for packaged native binaries."""

    def has_ext_modules(self):
        return True


class BinaryBdistWheel(bdist_wheel):
    """Emit py3/none ABI tag so one wheel works across Python 3 versions."""

    def get_tag(self):
        _, _, plat = super().get_tag()
        return "py3", "none", plat


setup(distclass=BinaryDistribution, cmdclass={"bdist_wheel": BinaryBdistWheel})
