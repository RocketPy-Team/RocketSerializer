import yaml


def search_nosecone(bs, elements):
    settings = {}
    nosecone = bs.find("nosecone")  # TODO: allow for multiple nosecones
    name = nosecone.find("name").text if nosecone else "NoseCone"
    cm = elements[name]["DistanceToCG"]

    nosecone = bs.find("nosecone")  # Why is it doing it twice?
    if nosecone == None:
        nosecones = list(
            filter(
                lambda x: x.find("name").text == "Nosecone", bs.findAll("transition")
            )
        )
        if len(nosecones) == 0:
            print("Could not fetch the nosecone")
            return
        nosecone = nosecones[0]

    length = float(nosecone.find("length").text)
    shape = nosecone.find("shape").text

    if shape == "haack":
        shape_parameter = float(nosecone.find("shapeparameter").text)
        shape = "Von Karman" if shape_parameter == 0.0 else "lvhaack"
        settings.update({"noseShapeParameter": shape_parameter})

    distanceToCM = cm

    settings = {
        "noseLength": length,
        "noseShape": shape,
        "noseDistanceToCM": distanceToCM,
    }
    print(
        f"[Nosecone] Found Nosecone| Configuration: \n{yaml.dump(settings, default_flow_style=False)}"
    )
    return settings
