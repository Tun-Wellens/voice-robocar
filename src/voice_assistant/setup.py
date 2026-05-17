from setuptools import setup

package_name = 'voice_assistant'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='360Lab',
    maintainer_email='user@todo.todo',
    description='Voice Assistant ROS 2 package',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'main_node = voice_assistant.main_node:main'
        ],
    },
)