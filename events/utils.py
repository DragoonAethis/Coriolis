from PIL import Image


def postprocess_image(image: Image) -> Image:
    """Perform image cropping and rescaling into reasonable values.
    This is a massive to do, as we don't have requirements for this yet."""
    width, height = image.size

    # Crop the image to a square if it's not one already:
    if width != height:
        if width > height:
            # +-+----+-+
            # | |    | |
            # +-+----+-+
            side = height
            lx, ly = (width - side) // 2, 0
            rx, ry = side + lx, height
        else:
            # +----+
            # |    |
            # +----+
            # |    |
            # |    |
            # +----+
            # |    |
            # +----+
            side = width
            lx, ly = 0, (height - side) // 2
            rx, ry = width, side + ly

        # crop() accepts (*top_left, *bottom_right) coords of a box:
        image = image.crop((lx, ly, rx, ry))
        width, height = image.size

    # At this point the image has correct proportions. Check if we
    # also need to downscale it (down to 1024x1024):
    if width > 1024 or height > 1024:
        image = image.resize((1024, 1024), resample=Image.LANCZOS)
        width, height = image.size

    return image
