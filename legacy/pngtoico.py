from PIL import Image

def convert_png_to_ico(png_path, ico_path):
    """Converts a PNG image to an ICO file.

    Args:
        png_path (str): Path to the input PNG image.
        ico_path (str): Path to the output ICO file.
    """
    try:
        png = Image.open(png_path)
        size = png.size
        # Create a new square image with transparent background
        ico = Image.new(mode="RGBA", size=(max(size), max(size)), color=(0, 0, 0, 0))
        # Paste the original image onto the center of the square image
        ico.paste(png, (int((max(size)-size[0])/2), int((max(size)-size[1])/2)))
        ico.save(ico_path, format='ICO', quality=100, sizes=[(16,16), (32,32), (48,48), (64,64)])
        print(f"Successfully converted {png_path} to {ico_path}")
    except FileNotFoundError:
        print(f"Error: PNG file not found at {png_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    png_file = "icon.png"  # Replace with your PNG file path
    ico_file = "output_icon.ico"  # Replace with your desired ICO file path
    convert_png_to_ico(png_file, ico_file)