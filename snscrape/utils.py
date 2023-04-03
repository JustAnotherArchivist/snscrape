def dict_map(input, keyMap):
	'''Return a new dict from an input dict and a {'input_key': 'output_key'} mapping'''

	return {outputKey: input[inputKey] for inputKey, outputKey in keyMap.items() if inputKey in input}
