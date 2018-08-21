import argparse
import logging
import snscrape.base
import snscrape.modules


logger = logging.getLogger(__name__)


def parse_args():
	parser = argparse.ArgumentParser(formatter_class = argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('-v', '--verbose', '--verbosity', dest = 'verbosity', action = 'count', default = 0, help = 'Increase output verbosity')
	parser.add_argument('--retry', '--retries', dest = 'retries', type = int, default = 3, metavar = 'N',
		help = 'When the connection fails or the server returns an unexpected response, retry up to N times with an exponential backoff')
	parser.add_argument('-n', '--max-results', dest = 'maxResults', type = int, metavar = 'N', help = 'Only return the first N results')

	subparsers = parser.add_subparsers(dest = 'scraper', help = 'The scraper you want to use')
	classes = snscrape.base.Scraper.__subclasses__()
	for cls in classes:
		subparser = subparsers.add_parser(cls.name, formatter_class = argparse.ArgumentDefaultsHelpFormatter)
		cls.setup_parser(subparser)
		subparser.set_defaults(cls = cls)
		classes.extend(cls.__subclasses__())

	args = parser.parse_args()

	# http://bugs.python.org/issue16308 / https://bugs.python.org/issue26510 (fixed in Python 3.7)
	if not args.scraper:
		raise RuntimeError('Error: no scraper specified')

	return args


def setup_logging(verbosity):
	rootLogger = logging.getLogger()

	# Set level
	if verbosity > 0:
		level = logging.INFO if verbosity == 1 else logging.DEBUG
		rootLogger.setLevel(level)
		for handler in rootLogger.handlers:
			handler.setLevel(level)

	# Create formatter
	formatter = logging.Formatter('{asctime}.{msecs:03.0f}  {levelname}  {name}  {message}', datefmt = '%Y-%m-%d %H:%M:%S', style = '{')

	# Add stream handler
	handler = logging.StreamHandler()
	handler.setFormatter(formatter)
	rootLogger.addHandler(handler)


def main():
	args = parse_args()
	setup_logging(args.verbosity)
	scraper = args.cls.from_args(args)

	i = 0
	for i, item in enumerate(scraper.get_items(), start = 1):
		print(item)
		if args.maxResults and i >= args.maxResults:
			logger.info(f'Exiting after {i} results')
			break
	else:
		logger.info(f'Done, found {i} results')
