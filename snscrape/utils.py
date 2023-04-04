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
