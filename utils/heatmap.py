import numpy as np
import cv2

def create_custom_colormap():
    colors = [
        [0, 0, 128],     # Dark Blue
        [0, 0, 255],     # Blue
        [0, 255, 255],   # Aqua
        [0, 255, 0],     # Green
        [255, 255, 0],   # Yellow
        [255, 0, 0]      # Red
    ]
    
    colormap = []
    for x in range(len(colors) - 1):
        r1, g1, b1 = colors[x]
        r2, g2, b2 = colors[x + 1]
        for i in np.linspace(0, 1, 256 // (len(colors) - 1), endpoint=False):
            r = int(r1 * (1 - i) + r2 * i)
            g = int(g1 * (1 - i) + g2 * i)
            b = int(b1 * (1 - i) + b2 * i)
            colormap.append([b, g, r])

    while len(colormap) < 256:
        colormap.append(colors[-1])
        
    custom_colormap = np.array(colormap, dtype=np.uint8).reshape(256, 1, 3)
    return custom_colormap
def generate_heatmap(background_path, playercoords, map_name="chernarus"):
    try:
        map_image = cv2.imread(background_path)
        if map_image is None:
            raise ValueError(f"Error loading image from path: {background_path}")

        height, width, _ = map_image.shape

        # Map dimensions for coordinate scaling
        map_dimensions = {
            "chernarus": 15360.0,
            "livonia": 12800.0,
            "sahkal": 12800.0 #Placeholder value until actual map size is known
        }
        
        map_size = map_dimensions.get(map_name.lower(), 15360.0)
        
        x_scale_factor = width / map_size
        y_scale_factor = height / map_size

        heatmap = np.zeros((height, width), dtype=np.float32)

        for coord in playercoords:
            # Livonia and Sakhal use X, Z; Chernarus uses X, Y
            if map_name.lower() in ["livonia", "sakhal"]:
                x, y = int(coord[0] * x_scale_factor), int((map_size - coord[2]) * y_scale_factor)
            else:
                x, y = int(coord[0] * x_scale_factor), int((map_size - coord[1]) * y_scale_factor)
            if 0 <= x < width and 0 <= y < height:
                cv2.circle(heatmap, (x, y), radius=5, color=1, thickness=-1) 

        heatmap = cv2.GaussianBlur(heatmap, (35, 35), 0)
        heatmap_normalized = cv2.normalize(heatmap, None, 0, 1, cv2.NORM_MINMAX, dtype=cv2.CV_32F)
        alpha_channel = np.clip(heatmap_normalized * 255, 0, 255).astype(np.uint8)
        heatmap_colored = cv2.applyColorMap(alpha_channel, create_custom_colormap())
        blue_mask = (heatmap_colored[:, :, 0] > 100) & (heatmap_colored[:, :, 1] < 100) & (heatmap_colored[:, :, 2] < 100)
        alpha_channel[blue_mask] = np.clip(alpha_channel[blue_mask] * 3, 0, 255)
        heatmap_rgba = cv2.merge((heatmap_colored[:, :, 0], heatmap_colored[:, :, 1], heatmap_colored[:, :, 2], alpha_channel))
        for y in range(height):
            for x in range(width):
                if heatmap_rgba[y, x, 3] > 0:
                    alpha = heatmap_rgba[y, x, 3] / 255.0
                    map_image[y, x] = (1 - alpha) * map_image[y, x] + alpha * heatmap_rgba[y, x, :3]

        cv2.imwrite('heatmap.jpg', map_image)

        return 'final_heatmap.jpg'
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None