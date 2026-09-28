from setuptools import setup

setup(
    name='atlas_power',
    version='0.1.0',
    packages=['atlas_power'],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/atlas_power']),
        ('share/atlas_power', ['package.xml']),
        ('share/atlas_power/launch', ['launch/atlas_power.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Atlas Autoware',
    maintainer_email='admin@atlasautoware.org',
    description='Battery state, E-stop and charging status, and lidar power for the Atlas car v2 boards',
    license='Apache-2.0',
    entry_points={'console_scripts': ['power_node = atlas_power.power_node:main']},
)
