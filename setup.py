from setuptools import setup, find_packages

setup(
    name='akanda-rug',
    version='0.1.5',
    description='Akanda Router Update Generator manages tenant routers',
    author='DreamHost',
    author_email='dev-community@dreamhost.com',
    url='http://github.com/dreamhost/akanda-rug',
    license='BSD',
    install_requires=[
        'netaddr>=0.7.5',
        'httplib2>=0.7.2',
        'python-neutronclient>=2.3.0,<3',
        'oslo.config',
        'kombu>=2.4.8'
    ],
    namespace_packages=['akanda'],
    packages=find_packages(exclude=['test']),
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'akanda-rug-service=akanda.rug.service:main',
            'akanda-rug-new=akanda.rug.main:main',
        ]
    },
)
