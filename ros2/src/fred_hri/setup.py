from setuptools import setup

setup(
    name='fred_hri', version='0.1.0', packages=['fred_hri'],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/fred_hri']),
        ('share/fred_hri', ['package.xml']),
        ('share/fred_hri/launch', ['launch/tracking.launch.py']),
    ],
    install_requires=['setuptools'],
    entry_points={'console_scripts': [
        f'{name} = fred_hri.{name}:main' for name in
        ('perception_node', 'hri_coordinator_node', 'display_gateway_node')
    ]},
)
