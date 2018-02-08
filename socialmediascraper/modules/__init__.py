import importlib
import os
import socialmediascraper.base


def _import_modules():
	files = os.listdir(__path__[0])
	for fn in files:
		if fn.endswith('.py') and fn != '__init__.py':
			# Import module if not already imported
			moduleName = f'socialmediascraper.modules.{fn[:-3]}'
			module = importlib.import_module(moduleName)


_import_modules()
