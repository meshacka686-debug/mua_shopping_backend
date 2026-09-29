from cloudinary_storage.storage import (
    MediaCloudinaryStorage,
    VideoMediaCloudinaryStorage,
)


class CloudinaryImageStorage(MediaCloudinaryStorage):
    pass


class CloudinaryVideoStorage(VideoMediaCloudinaryStorage):
    pass
