def rgba_to_hex(rgba):
    """
    Convert an RGBA tuple to a HEX string.

    Args:
    rgba (tuple): A tuple containing red, green, blue, and alpha values (each 0-255).

    Returns:
    str: The HEX string representation of the color.
    """
    print(f'#{rgba[0]:02x}{rgba[1]:02x}{rgba[2]:02x}{rgba[3]:02x}')
    return f'#{rgba[0]:02x}{rgba[1]:02x}{rgba[2]:02x}{rgba[3]:02x}'
