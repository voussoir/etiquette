from voussoirkit import imagetools
from voussoirkit import vlogging

vlogging.basic_config(vlogging.INFO)

import etiquette

P = etiquette.photodb.PhotoDB()

with P.transaction:
    try:
        CAMERA = P.get_tag('camera')
    except etiquette.exceptions.NoSuchTag:
        CAMERA = P.new_tag('camera')

    try:
        LENS = P.get_tag('lens')
    except etiquette.exceptions.NoSuchTag:
        LENS = P.new_tag('lens')

    for photo in P.search(extension=['jpeg', 'jpg'], yield_albums=False):
        if not photo.real_path.exists:
            continue
        exif = imagetools.exifread(photo.real_path)
        camera_make = exif.get('Image Make')
        camera_model = exif.get('Image Model')
        camera_make = camera_make.values if camera_make else ''
        camera_model = camera_model.values if camera_model else ''
        camera = ' '.join([camera_make, camera_model]).strip().replace('.', '')
        lens = exif.get('EXIF LensModel')
        lens = (lens.values if lens else '').replace('.', '')
        if camera:
            try:
                camera_tag = P.get_tag(camera)
            except etiquette.exceptions.NoSuchTag:
                camera_tag = P.new_tag(camera)
                CAMERA.add_child(camera_tag)
            photo.add_tag(camera_tag)
        if lens:
            try:
                lens_tag = P.get_tag(lens)
            except etiquette.exceptions.NoSuchTag:
                lens_tag = P.new_tag(lens)
                LENS.add_child(lens_tag)
            photo.add_tag(lens_tag)
