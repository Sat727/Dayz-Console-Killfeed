from utils.locations import Locations
import math
def getClosestLocation(coords, locations=Locations):
    closest = ['None', 999999999]
    coords = str(coords).split(';')
    coords.pop(2)
    for i in Locations['destinations']:
        value = math.sqrt((i['coord'][0] - float(coords[0])) ** 2 + (i['coord'][1] - float(coords[1])) ** 2)
        if value < closest[1]:
             print(f"Closest is now {i['name']} with distance {value}")
             closest = [i['name'], value]
    return closest
