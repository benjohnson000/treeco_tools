"""Create a multi-size Windows icon from the application logo."""

from pathlib import Path

from PIL import Image


SOURCE = Path(__file__).with_name("logo.png")
DESTINATION = Path(__file__).with_name("icon.ico")
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Application logo not found: {SOURCE}")
    with Image.open(SOURCE) as image:
        image.convert("RGBA").save(DESTINATION, format="ICO", sizes=SIZES)


if __name__ == "__main__":
    main()
