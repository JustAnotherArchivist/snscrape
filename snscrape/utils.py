def dict_map(input, keyMap):
	'''Return a new dict from an input dict and a {'input_key': 'output_key'} mapping'''

	return {outputKey: input[inputKey] for inputKey, outputKey in keyMap.items() if inputKey in input}


def snake_to_camel(**kwargs):
	'''Return a new dict from kwargs with snake_case keys replaced by camelCase'''

	out = {}
	for key, value in kwargs.items():
		keyParts = key.split('_')
		for i in range(1, len(keyParts)):
			keyParts[i] = keyParts[i][:1].upper() + keyParts[i][1:]
		out[''.join(keyParts)] = value
	return out


def nonempty_string_arg(name):
	'''An argparse argument type factory for a non-empty string argument. The supplied `name` is used for the internal function name, resulting in better error messages.'''

	def f(s):
		s = s.strip()
		if s:
			return s
		raise ValueError('must not be an empty string')
	f.__name__ = name
	return f


def module_deprecation_helper(all, **names):
	'''A helper function to generate the relevant module __getattr__ and __dir__ functions for handling deprecated names'''

	def __getattr__(name):
		if name in names:
			warnings.warn(f'{name} is deprecated, use {names[name].__name__} instead', DeprecatedFeatureWarning, stacklevel = 2)
			return names[name]
		raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
	def __dir__():
		return sorted(all + list(names.keys()))
	return __getattr__, __dir__
