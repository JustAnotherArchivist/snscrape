import pkg_resources


try:
	__version__ = pkg_resources.get_distribution('snscrape').version
except pkg_resources.DistributionNotFound:
	__version__ = None
