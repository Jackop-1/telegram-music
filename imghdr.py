import io

def what(file, h=None):
    if h is None:
        if isinstance(file, (str, bytes)):
            with open(file, 'rb') as f:
                h = f.read(32)
        elif isinstance(file, io.BytesIO):
            h = file.getvalue()[:32]
        else:
            return None

    if h[:4] == b'\xff\xd8\xff\xe0' or h[:4] == b'\xff\xd8\xff\xe1':
        return 'jpeg'
    if h[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if h[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'
    return None
