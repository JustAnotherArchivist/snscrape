import setuptools


setuptools.setup(
	name = 'socialmediascraper',
	version = '0.0-dev',
	description = 'A social media scraper',
	packages = ['socialmediascraper'],
	install_requires = ['requests', 'lxml', 'beautifulsoup4'],
	entry_points = {
		'console_scripts': [
			'smscrape = socialmediascraper:main',
		],
	},
)
