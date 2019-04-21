import setuptools


setuptools.setup(
	name = 'snscrape',
	version = '0.2.0',
	description = 'A social networking service scraper',
	author = 'JustAnotherArchivist',
	url = 'https://github.com/JustAnotherArchivist/snscrape',
	classifiers = [
		'Development Status :: 4 - Beta',
		'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
		'Programming Language :: Python :: 3.6',
	],
	packages = ['snscrape', 'snscrape.modules'],
	install_requires = ['requests[socks]', 'lxml', 'beautifulsoup4'],
	entry_points = {
		'console_scripts': [
			'snscrape = snscrape.cli:main',
		],
	},
)
