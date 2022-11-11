import yaml

def search_trapezoidal_fins(bs, elements, idx):
    trapezoidal_fins_parameters = {}
    fins = bs.findAll('trapezoidfinset')
    print(f'[AddFins]- {len(fins)} detected')

    for idx, fin in enumerate(fins):
        element_label = fin.find('name').text
        element = elements[element_label]

        n_fin = int(fin.find('fincount').text)
        root_chord = float(fin.find('rootchord').text)
        tip_chord = float(fin.find('tipchord').text)
        span = float(fin.find('height').text)
        sweep_length = float(fin.find('sweeplength').text) if fin.find('sweeplength') else None
        sweep_angle = float(fin.find('sweepangle').text) if fin.find('sweepangle') else None
        fin_distance_to_cm = element["DistanceToCG"]
        fin_parameter = {
            f'finN{idx}': n_fin,
            f'finRootChord{idx}': root_chord,
            f'finTipChord{idx}': tip_chord,
            f'finSpan{idx}': span,
            f'finDistanceToCm{idx}': fin_distance_to_cm,
            f'finSweepLength{idx}': sweep_length,
            f'finSweepAngle{idx}': sweep_angle
        }

        trapezoidal_fins_parameters.update(fin_parameter)
        print(f'[AddFins][{idx}] Configuration: \n{yaml.dump(fin_parameter, default_flow_style=False)}')
    print(f'[AddFins]- Finished')
    return trapezoidal_fins_parameters