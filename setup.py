import setuptools


setuptools.setup(
	name = 'snscrape',
	version = '0.0-dev',
	description = 'A social network service scraper',
	packages = ['snscrape'],
	install_requires = ['requests', 'lxml', 'beautifulsoup4'],
	entry_points = {
		'console_scripts': [
			'snscrape = snscrape.cli:main',
		],
	},
)
