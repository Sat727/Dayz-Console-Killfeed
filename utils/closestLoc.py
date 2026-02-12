from utils.locations import Locations
import math

def getClosestLocation(coords, map_name="chernarus"):
    """
    Find the closest location to given coordinates.
    
    Args:
        coords: Formatted coordinates string (e.g., "6100.9;4136.1")
        map_name: Map name (chernarus, livonia, sahkal, etc.)
    
    Returns:
        List: [location_name, distance]
    """
    # Map lowercase names to Locations dictionary keys
    map_key_mapping = {
        "chernarus": "Chernarus",
        "livonia": "Livonia",
        "sahkal": "Sahkal",
    }
    
    map_key = map_key_mapping.get(map_name.lower(), "Chernarus")
    
    # Get locations for the specified map
    if map_key not in Locations:
        return ['None', 999999999]
    
    closest = ['None', 999999999]
    coords_list = str(coords).split(';')
    
    if len(coords_list) < 2:
        return ['None', 999999999]
    
    try:
        coord_x = float(coords_list[0])
        coord_z = float(coords_list[1])
    except (ValueError, IndexError):
        return ['None', 999999999]
    
    for location in Locations[map_key]:
        if 'coord' in location:
            distance = math.sqrt((location['coord'][0] - coord_x) ** 2 + (location['coord'][1] - coord_z) ** 2)
            if distance < closest[1]:
                closest = [location['name'], distance]
    
    return closest
