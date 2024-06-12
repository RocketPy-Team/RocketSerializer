import json

path_file1 = '/home/jmach/RocketSerializer/examples/rocket_with_elliptical_fins/parameters.json'
path_file2 = '/home/jmach/RocketSerializer/examples/EPFL--BellaLui--2020/parameters.json'
with open(path_file1, 'r', encoding="utf-8") as f: 
            parameters = json.load(f)

trapezoidal_fins_check = False
elliptical_fins_check = False
if len(parameters["trapezoidal_fins"]) > 0:
    trapezoidal_fins_check = True
if len(parameters["elliptical_fins"]) > 0:
    elliptical_fins_check = True

if trapezoidal_fins_check:
        print(" trapezoidal funciona!")
else:
       print("trapezoidal no funciona!")

if elliptical_fins_check:
        print("elliptical funciona!")
else:
       print("elliptical no funciona!")


