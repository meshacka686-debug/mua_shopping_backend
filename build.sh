#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

python manage.py migrate

python manage.py shell -c '
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage

buffer = BytesIO()
Image.new("RGB", (50, 50), "white").save(buffer, format="JPEG")
buffer.seek(0)

test_file = SimpleUploadedFile(
    "render_cloudinary_test.jpg",
    buffer.getvalue(),
    content_type="image/jpeg",
)

name = default_storage.save(
    "cloudinary_test/render_cloudinary_test.jpg",
    test_file,
)

print("CLOUDINARY RENDER TEST: UPLOAD SUCCESS")
print("Saved:", name)
print("URL:", default_storage.url(name))

default_storage.delete(name)

print("CLOUDINARY RENDER TEST: FILE DELETED")
'
