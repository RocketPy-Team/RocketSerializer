import yaml

def search_nosecone(bs, elements):
    nosecone_configuration = {}
    nosecone = bs.find('nosecone')
    element_name = nosecone.find('name').text if nosecone else 'Nosecone'
    cm = elements[element_name]['DistanceToCG']

    nosecone = bs.find('nosecone')
    if nosecone == None:
        nosecones = list(filter(lambda x: x.find('name').text == 'Nosecone', bs.findAll('transition')))
        if len(nosecones) == 0:
            print('Could not fetch the nosecone')
            return
        nosecone = nosecones[0]
    nosecone_length = float(nosecone.find('length').text)
    nosecone_shape = nosecone.find('shape').text
    if nosecone_shape == 'haack':
        nosecone_shape_parameter = float(nosecone.find('shapeparameter').text)
        nosecone_shape = 'Von Karman' if nosecone_shape_parameter == 0.0 else 'lvhaack'
        nosecone_configuration.update({'noseShapeParameter': nosecone_shape_parameter})
    nosecone_distanceToCM = cm

    nosecone_configuration = {
            'noseLength': nosecone_length,
            'noseShape': nosecone_shape,
            'noseDistanceToCM': nosecone_distanceToCM
    }
    print(f'[Nosecone] Found Nosecone| Configuration: \n{yaml.dump(nosecone_configuration, default_flow_style=False)}')
    return nosecone_configuration
